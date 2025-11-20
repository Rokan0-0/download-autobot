# app.py - FastAPI Server with Sequential Queue System

import sys
import threading
import time
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

# Import our scraper
from scrapers import nkiri

app = FastAPI()

# --- CONFIGURATION ---
# Enable CORS so index.html can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL STATE ---
JOB_QUEUE = []          # Stores list of URLs to download
CURRENT_JOB = None      # Stores the URL currently being downloaded
IS_WORKER_RUNNING = False # Flag to check if the background thread is alive
ACTIVE_JOBS = {}        # History of job statuses (for the UI)

def process_queue_worker():
    """
    The Background Worker.
    It runs as long as there are items in the queue.
    When the queue is empty, it shuts itself down.
    """
    global IS_WORKER_RUNNING, CURRENT_JOB

    print("\n👷 Worker Thread Started.")
    
    while len(JOB_QUEUE) > 0:
        # 1. Pop the next URL from the queue (FIFO - First In, First Out)
        url_data = JOB_QUEUE.pop(0)
        job_id = url_data['id']
        url = url_data['url']
        
        CURRENT_JOB = url
        ACTIVE_JOBS[job_id] = "RUNNING"
        print(f"\n🚀 Processing Job {job_id}: {url}")
        print(f"📊 Items remaining in queue: {len(JOB_QUEUE)}")

        try:
            # 2. Run the Scraper (This blocks until finished)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                nkiri.download_series(context, url)
            
            ACTIVE_JOBS[job_id] = "COMPLETED"
            print(f"✅ Job {job_id} Finished.")

        except Exception as e:
            print(f"❌ Job {job_id} Failed: {e}")
            ACTIVE_JOBS[job_id] = "FAILED"
    
    # 3. Cleanup when queue is empty
    CURRENT_JOB = None
    IS_WORKER_RUNNING = False
    print("💤 Queue empty. Worker Thread going to sleep.")


@app.get("/")
def home():
    return {"message": "Download Autobot Queue System is Running!"}

@app.post("/api/download")
def queue_download(url: str = Form(...)):
    """
    Receives a URL and adds it to the Queue.
    If the worker isn't running, it starts the worker.
    """
    global IS_WORKER_RUNNING

    if "thenkiri.com" not in url:
        return {"status": "error", "message": "Only thenkiri.com URLs are supported."}
    
    # 1. Create Job Object
    job_id = f"job-{int(time.time())}" 
    job_data = {"id": job_id, "url": url}
    
    # 2. Add to Queue
    JOB_QUEUE.append(job_data)
    ACTIVE_JOBS[job_id] = "QUEUED"
    
    position_in_queue = len(JOB_QUEUE)
    
    print(f"\n📥 Job {job_id} added to queue. Position: {position_in_queue}")

    # 3. Wake up the Worker if it's sleeping
    if not IS_WORKER_RUNNING:
        IS_WORKER_RUNNING = True
        worker_thread = threading.Thread(target=process_queue_worker)
        worker_thread.start()
        message = "Download started immediately."
    else:
        message = f"Added to queue. Position: {position_in_queue}"

    return {
        "status": "success",
        "message": message,
        "job_id": job_id,
        "queue_position": position_in_queue
    }

@app.get("/api/status")
def get_system_status():
    """
    Returns the global status of the queue.
    """
    return {
        "worker_running": IS_WORKER_RUNNING,
        "current_job": CURRENT_JOB,
        "queue_length": len(JOB_QUEUE),
        "queue_items": JOB_QUEUE
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)