# app.py - The Pro Edition (Now with AnimePahe Support)

import sys
import time
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from playwright.sync_api import sync_playwright

# Import BOTH scrapers
from scrapers import nkiri, animepahe  # <--- IMPORTED HERE

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL STATE ---
MAX_CONCURRENT = 3
ACTIVE_JOBS = {}
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)

# --- HELPER: AUTO-INSTALL BROWSERS ---
def install_browsers_if_needed():
    print("⚙️  Checking Playwright browsers...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                p.chromium.launch(headless=True)
                print("✅ Browsers found.")
            except Exception:
                print("⬇️  First run detected. Installing Browsers...")
                os.system("playwright install chromium")
    except Exception as e:
        print(f"Error checking browsers: {e}")

# --- HELPER: GET LOCAL IP ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- JOB RUNNER (runs per-job in a thread pool) ---
def run_single_job(job_data):
    """Process a single download job. Called by the ThreadPoolExecutor."""
    job_id = job_data['id']
    url = job_data['url']
    job_type = job_data.get('type', 'nkiri')

    ACTIVE_JOBS[job_id] = "RUNNING"
    print(f"\n🚀 Processing Job {job_id} [{job_type}]: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            # --- ROUTER LOGIC ---
            if job_type == "nkiri":
                nkiri.download_series(context, url)
            elif job_type == "animepahe":
                animepahe.download_single_episode(context, url)
            # --------------------

        ACTIVE_JOBS[job_id] = "COMPLETED"
        print(f"✅ Job {job_id} Finished.")

    except Exception as e:
        print(f"❌ Job {job_id} Failed: {e}")
        ACTIVE_JOBS[job_id] = "FAILED"

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: index.html not found.</h1>"

@app.get("/api/status")
def get_system_status():
    running = sum(1 for s in ACTIVE_JOBS.values() if s == "RUNNING")
    return {
        "active_downloads": running,
        "max_concurrent": MAX_CONCURRENT
    }

@app.post("/api/download")
def queue_download(url: str = Form(...)):
    # --- DETERMINE JOB TYPE ---
    job_type = "unknown"
    if "thenkiri.com" in url:
        job_type = "nkiri"
    elif "animepahe" in url:
        job_type = "animepahe"
    else:
        return {"status": "error", "message": "URL not supported (only Thenkiri & AnimePahe)."}
    # --------------------------

    job_id = f"job-{int(time.time())}"
    job_data = {"id": job_id, "url": url, "type": job_type}

    ACTIVE_JOBS[job_id] = "QUEUED"
    executor.submit(run_single_job, job_data)

    running = sum(1 for s in ACTIVE_JOBS.values() if s == "RUNNING")
    print(f"\n📥 Job submitted ({job_type}). Active downloads: {running}/{MAX_CONCURRENT}")

    return {"status": "success", "message": "Download started immediately.", "job_id": job_id, "queue_position": 0}

if __name__ == "__main__":
    import uvicorn
    install_browsers_if_needed()
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f"📱 MOBILE ACCESS: http://{local_ip}:8000")
    print(f"💻 LOCAL ACCESS:  http://127.0.0.1:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)