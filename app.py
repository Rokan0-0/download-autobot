# app.py - The FastAPI Server with CORS Fixed

import sys
import threading
import time
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

# Import the specific scraper we need
from scrapers import nkiri

# --- GLOBAL JOB QUEUE ---
ACTIVE_JOBS = {}
app = FastAPI()

# --- ENABLE CORS ---
# This allows your local index.html file to talk to this server without security errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (POST, GET, etc.)
    allow_headers=["*"],
)

def run_download_task(url: str, job_id: str):
    """
    This function contains the core logic and runs in a separate thread.
    """
    try:
        # Playwright must be initialized inside the thread that uses it
        with sync_playwright() as p:
            # You can change headless=False if you want to see the browser open
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context()
            
            # Execute the scraper engine
            nkiri.download_series(context, url)
            
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        ACTIVE_JOBS[job_id] = "FAILED"
    
    # Thread finishes, context manager closes browser automatically
    ACTIVE_JOBS[job_id] = "COMPLETED"


@app.get("/")
def home():
    """Simple API status check."""
    return {"message": "Download Autobot API is Running!"}


@app.post("/api/download")
def start_download(url: str = Form(...)):
    """API endpoint to receive a URL and start the download job in the background."""
    
    # Simple validation
    if "thenkiri.com" not in url:
        return {"status": "error", "message": "Only thenkiri.com URLs are supported in this version."}
    
    # 1. Generate a unique ID for the job
    job_id = f"job-{int(time.time())}" 
    
    # 2. Add the job to our status tracker
    ACTIVE_JOBS[job_id] = "RUNNING"
    print(f"\n--- Starting Job {job_id} for URL: {url} ---")
    
    # 3. Start the download process in a new thread
    thread = threading.Thread(target=run_download_task, args=(url, job_id))
    thread.start()
    
    # 4. Immediately return a success message
    return {
        "status": "success",
        "message": "Download job started in background.",
        "job_id": job_id
    }

@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    """Endpoint to check the status of a running job."""
    status = ACTIVE_JOBS.get(job_id, "NOT_FOUND")
    return {"job_id": job_id, "status": status}


if __name__ == "__main__":
    import uvicorn
    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000)