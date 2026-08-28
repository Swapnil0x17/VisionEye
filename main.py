from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import pytesseract
import os
from PIL import Image
import io
import piexif
import requests
import base64
import math
import re
from dotenv import load_dotenv
load_dotenv()
from typing import Optional, List

# ---------- Set Tesseract ----------
# Change this path if your Tesseract is installed elsewhere.
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'D:\Visioneyee\tesseract\tesseract.exe'
else:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# ---------- Groq API key (loaded from .env) ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- GPS helper ----------
def convert_to_degrees(value):
    deg = value[0][0] / value[0][1]
    min = value[1][0] / value[1][1]
    sec = value[2][0] / value[2][1]
    return deg + (min / 60.0) + (sec / 3600.0)

def format_rational(value):
    try:
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
            if den != 0:
                return f"{num / den:.2f}"
            else:
                return str(value)
        return str(value)
    except:
        return str(value)

def clean_ai_summary(text: str) -> str:
    """Remove all meta-commentary, numbered lists, bullet points, and internal reasoning."""
    patterns = [
        r'The user wants[^.]*\.',
        r'I need to provide[^.]*\.',
        r'I will analyze[^.]*\.',
        r'Here is my analysis[^.]*\.',
        r'As an OSINT analyst[^.]*\.',
        r'Here is the summary[^.]*\.',
        r'Based on the image[^.]*\.',
        r'Looking at the image[^.]*\.',
        r"Here's what I see[^.]*\.",
        r'Let me analyze[^.]*\.',
        r'I can see[^.]*\.',
        r'The image shows[^.]*\.',
        r'Analyze the Image[^.]*\.',
        r'Subject[^:]*:',
        r'Background[^:]*:',
        r'Sky[^:]*:',
        r'Lighting[^:]*:',
        r'Details[^:]*:',
        r'Draft \d+[^:]*:',
        r'Refining for constraints[^:]*:',
        r'\*\*[^*]*\*\*',
        r'^\d+\.\s*',
        r'^•\s*',
        r'^-\s*',
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^SUMMARY:\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    groq_api_key: Optional[str] = Form(None)
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # ---------- EXIF ----------
        exif_data = {}
        try:
            exif_dict = piexif.load(contents)
            if exif_dict:
                for ifd in exif_dict:
                    if exif_dict[ifd] is not None:
                        for tag, value in exif_dict[ifd].items():
                            tag_name = piexif.TAGS[ifd].get(tag, {}).get('name', str(tag))
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode('utf-8').strip('\x00')
                                except:
                                    value = str(value)
                            exif_data[tag_name] = str(value)
        except Exception as e:
            print("EXIF load error:", e)

        # ---------- GPS ----------
        gps_lat = exif_data.get('GPSLatitude', None)
        gps_lat_ref = exif_data.get('GPSLatitudeRef', None)
        gps_lon = exif_data.get('GPSLongitude', None)
        gps_lon_ref = exif_data.get('GPSLongitudeRef', None)

        gps_decimal = None
        map_url = None
        gps_city = None
        gps_country = None

        if gps_lat and gps_lon:
            try:
                lat_tuple = eval(gps_lat)
                lon_tuple = eval(gps_lon)
                lat = convert_to_degrees(lat_tuple)
                lon = convert_to_degrees(lon_tuple)
                if gps_lat_ref and gps_lat_ref == 'S':
                    lat = -lat
                if gps_lon_ref and gps_lon_ref == 'W':
                    lon = -lon
                gps_decimal = f"{lat:.6f}, {lon:.6f}"
                map_url = f"https://www.google.com/maps?q={lat},{lon}"
                try:
                    geo_resp = requests.get(
                        f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10",
                        headers={"User-Agent": "VisionEye/1.0"},
                        timeout=10
                    )
                    if geo_resp.status_code == 200:
                        geo_data = geo_resp.json()
                        if 'address' in geo_data:
                            addr = geo_data['address']
                            gps_city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('state_district') or None
                            gps_country = addr.get('country') or None
                except:
                    pass
            except:
                pass

        # ---------- Metadata ----------
        camera = exif_data.get('Make', 'N/A')
        if camera == 'N/A':
            camera = exif_data.get('Software', 'N/A')
        if camera.startswith("b'") and camera.endswith("'"):
            camera = camera[2:-1]

        model = exif_data.get('Model', 'N/A')
        lens = exif_data.get('LensModel', 'N/A')
        date = exif_data.get('DateTime', 'N/A')
        if date == 'N/A':
            date = exif_data.get('DateTimeOriginal', 'N/A')
        if date.startswith("b'") and date.endswith("'"):
            date = date[2:-1]

        alt = format_rational(exif_data.get('GPSAltitude', 'N/A'))
        iso = exif_data.get('ISOSpeedRatings', 'N/A')
        focal = format_rational(exif_data.get('FocalLength', 'N/A'))
        aperture = format_rational(exif_data.get('FNumber', 'N/A'))
        shutter = format_rational(exif_data.get('ExposureTime', 'N/A'))

        # ---------- OCR ----------
        gray = image.convert('L')
        ocr_data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

        ocr_results = []
        for i in range(len(ocr_data['text'])):
            if int(ocr_data['conf'][i]) > 30:
                text = ocr_data['text'][i].strip()
                if text:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    coord_str = f"[{x},{y}] → [{x+w},{y}] → [{x+w},{y+h}] → [{x},{y+h}]"
                    ocr_results.append({
                        "text": text,
                        "confidence": round(ocr_data['conf'][i] / 100, 2),
                        "coordinates": coord_str
                    })

        # ---------- AI Reasoning (Ultra-clean prompt) ----------
        api_key = groq_api_key if groq_api_key and groq_api_key.strip() else GROQ_API_KEY

        summary = "No summary available."
        locations = []

        if api_key:
            try:
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()

                location_context = ""
                if gps_city or gps_country:
                    location_context = f"\nNote: EXIF GPS indicates this photo was taken near {gps_city or 'unknown city'}, {gps_country or 'unknown country'}."

                user_prompt = f"""Provide exactly two things about this image:

                1. A 3-4 sentence factual description of what the image shows. Be specific.
                2. A list of 3-5 possible places this image could have been taken, based on visual clues like architecture, vegetation, terrain, or landmarks. If GPS is available, include it.{location_context}

                Format your response exactly like this:
                DESCRIPTION: (your description here)
                LOCATIONS: (comma separated list)

                Do not include any other text, analysis steps, or meta-commentary."""

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "qwen/qwen3.6-27b",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                            ]
                        }
                    ],
                    "max_tokens": 250,
                    "temperature": 0.2
                }
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    full = resp.json()['choices'][0]['message']['content']
                    print("AI Raw Response:", full)  # Debug

                    if "DESCRIPTION:" in full:
                        desc_part = full.split("DESCRIPTION:")[1]
                        if "LOCATIONS:" in desc_part:
                            summary = desc_part.split("LOCATIONS:")[0].strip()
                            loc_part = full.split("LOCATIONS:")[1].strip()
                            locations = [loc.strip() for loc in loc_part.split(',') if loc.strip()]
                        else:
                            summary = desc_part.strip()
                    elif "SUMMARY:" in full:
                        summary_part = full.split("SUMMARY:")[1]
                        if "LOCATIONS:" in summary_part:
                            summary = summary_part.split("LOCATIONS:")[0].strip()
                            loc_part = full.split("LOCATIONS:")[1].strip()
                            locations = [loc.strip() for loc in loc_part.split(',') if loc.strip()]
                        else:
                            summary = summary_part.strip()
                    else:
                        summary = clean_ai_summary(full)
                        lines = full.strip().split('\n')
                        for line in lines:
                            if any(keyword in line.lower() for keyword in ['location', 'place', 'country', 'city', 'region']):
                                parts = re.split(r'[:,]', line)
                                if len(parts) > 1:
                                    locations.extend([p.strip() for p in parts[1:] if p.strip()])

                    summary = clean_ai_summary(summary)
                    if not summary or len(summary) < 10:
                        summary = "Image analysis complete. No description available."
                else:
                    summary = f"AI error: {resp.status_code}"
            except Exception as e:
                summary = f"AI failed: {str(e)}"

        # If GPS city/country available, prepend to locations
        if gps_city or gps_country:
            gps_loc = []
            if gps_city:
                gps_loc.append(gps_city)
            if gps_country:
                gps_loc.append(gps_country)
            if gps_loc:
                gps_str = ', '.join(gps_loc)
                if gps_str not in locations:
                    locations = [gps_str] + locations

        # Remove duplicates
        locations = list(dict.fromkeys(locations))
        locations = [loc for loc in locations if loc and len(loc) > 1]

        # ---------- Reverse search links ----------
        img_b64 = base64.b64encode(contents).decode()
        google_lens_url = f"https://lens.google.com/upload?image=data:image/jpeg;base64,{img_b64}"
        tineye_url = "https://tineye.com/"
        yandex_url = "https://yandex.com/images/search?source=collections&rpt=imageview"
        bing_url = "https://www.bing.com/visualsearch"

        return {
            "success": True,
            "summary": summary,
            "locations": locations,
            "gps_decimal": gps_decimal,
            "gps_city": gps_city,
            "gps_country": gps_country,
            "map_url": map_url,
            "metadata": {
                "Camera": camera,
                "Model": model,
                "Lens": lens,
                "Date": date,
                "GPS": gps_decimal if gps_decimal else "N/A",
                "Altitude": alt,
                "ISO": iso,
                "FocalLength": focal,
                "Aperture": aperture,
                "ShutterSpeed": shutter,
                "Dimensions": f"{image.width} x {image.height}",
                "Size": f"{len(contents) / 1024:.1f} KB"
            },
            "ocr": ocr_results,
            "reverse_search": [
                {"site": "Google Lens", "url": google_lens_url},
                {"site": "TinEye", "url": tineye_url},
                {"site": "Yandex", "url": yandex_url},
                {"site": "Bing Visual Search", "url": bing_url}
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/health")
def health():
    return {"status": "ok"}