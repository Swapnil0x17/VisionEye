# VisionEye – AI Image OSINT Tool

**See Beyond. Know Everything.**

VisionEye is a free, open‑source intelligence (OSINT) tool that extracts hidden information from images.  
Upload any image and instantly get:

- 🧠 **AI Reasoning** – clean, factual description.
- 📝 **Smart OCR** – text extraction with bounding‑box coordinates.
- 📸 **EXIF Metadata** – camera, GPS, date, ISO, aperture.
- 🗺️ **GPS to Location** – city/country via OpenStreetMap.
- 🌍 **Possible Locations** – AI‑guessed places (even without EXIF).
- 🔍 **Reverse Image Search** – Google Lens, TinEye, Yandex, Bing.

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python)
- **OCR:** Tesseract
- **AI:** Groq (Qwen vision model)
- **Frontend:** HTML5, CSS3, JavaScript
- **Hosting:** Local or deploy anywhere (Fly.io, Render, Railway)

---

## 🚀 Quick Start (Local)

1. Clone the repository  
   `git clone https://github.com/Swapnil0x17/VisionEye.git`
2. Create a virtual environment  
   `python -m venv venv`
3. Activate it (Windows)  
   `venv\Scripts\Activate.ps1`
4. Install dependencies  
   `pip install -r requirements.txt`
5. Set your Groq API key in `.env` (see above)
6. Place Tesseract in `./tesseract` or install system‑wide
7. Run the server  
   `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
8. Open `http://127.0.0.1:8000` in your browser

---

## 👨‍💻 Contributors

- **Swapnil** ([@Swapnil0x17](https://github.com/Swapnil0x17)) – Backend, AI integration, OCR, API
- **Hasan Ahmed** ([@Iamhasan69](https://github.com/Iamhasan69)) – Frontend, UI/UX, Testing, Design

---

## 📜 License

MIT – Free for everyone.

---

**Made ❤️ by Swapnil & Hasan**