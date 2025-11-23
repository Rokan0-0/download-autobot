# app.py - The Pro Edition (Now with AnimePahe Support)

import sys
import threading
import time
import os
import socket
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
JOB_QUEUE = []
ACTIVE_JOBS = {}
IS_WORKER_RUNNING = False
CURRENT_JOB = None

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

# --- WORKER THREAD ---
def process_queue_worker():
    global IS_WORKER_RUNNING, CURRENT_JOB
    print("\n👷 Worker Thread Started.")
    
    while len(JOB_QUEUE) > 0:
        url_data = JOB_QUEUE.pop(0)
        job_id = url_data['id']
        url = url_data['url']
        job_type = url_data.get('type', 'nkiri') # Default to nkiri
        
        CURRENT_JOB = url
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
    
    CURRENT_JOB = None
    IS_WORKER_RUNNING = False
    print("💤 Queue empty. Worker Thread sleeping.")

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
    return {
        "worker_running": IS_WORKER_RUNNING,
        "queue_length": len(JOB_QUEUE)
    }

@app.post("/api/download")
def queue_download(url: str = Form(...)):
    global IS_WORKER_RUNNING

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
    
    JOB_QUEUE.append(job_data)
    ACTIVE_JOBS[job_id] = "QUEUED"
    position = len(JOB_QUEUE)
    
    print(f"\n📥 Job added ({job_type}). Position: {position}")

    if not IS_WORKER_RUNNING:
        IS_WORKER_RUNNING = True
        t = threading.Thread(target=process_queue_worker)
        t.start()
        msg = "Download started immediately."
    else:
        msg = f"Added to queue. Position: {position}"

    return {"status": "success", "message": msg, "job_id": job_id, "queue_position": position}

if __name__ == "__main__":
    import uvicorn
    install_browsers_if_needed()
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f"📱 MOBILE ACCESS: http://{local_ip}:8000")
    print(f"💻 LOCAL ACCESS:  http://127.0.0.1:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)