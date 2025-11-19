import time
import os
from playwright.sync_api import sync_playwright, TimeoutError

# --- This is the variable you can adjust ---
WAIT_TIME_ON_LIMIT = 900  # 15 minutes

def download_episode(page, context, download_link_element):
    """
    Tries to navigate the 3-step process for ONE episode.
    (This function is proven to work for Ep 1)
    """
    try:
        # --- Step 1: Click the "Download Episode" link ---
        print("Clicking 'Download Episode' link...")
        download_link_element.click()
        
        page2 = None
        print("Waiting for 'downloadwella.com' tab to appear...")

        # Poll for 10 seconds to find the new tab
        for _ in range(10): 
            all_pages = context.pages
            found = False
            for p in all_pages:
                if "downloadwella.com" in p.url:
                    page2 = p
                    found = True
                    break 
            if found:
                break 
            
            time.sleep(1) # Wait 1 second and try again

        if not page2:
            print("❌ Error: Could not find the 'downloadwella.com' page after 10 seconds.")
            for p in context.pages:
                if p != page and "thenkiri.com" not in p.url:
                    if not p.is_closed(): p.close()
            return # Stop this episode download

        print(f"Switched to correct tab: {page2.url}")
        page2.bring_to_front()

        # Close all other ad pages
        for p in context.pages:
            if p != page and p != page2: 
                if not p.is_closed():
                    print(f"Closing ad tab: {p.url}")
                    p.close()
        
        page2.wait_for_load_state()

        # --- Step 2: Click "Create download link" ---
        print("Clicking 'Create download link'...")
        page2.get_by_text("Create download link").click(timeout=15000)
        
        page2.wait_for_load_state()

        # --- Step 3: Click "Start download" ---
        print("Clicking 'Start download'...")
        
        with page2.expect_download(timeout=15000) as download_info:
            page2.click("#direct_link")
        
        download = download_info.value
        
        file_path = os.path.join("downloads", download.suggested_filename)
        download.save_as(file_path)
        print(f"✅ Success! File saved to: {file_path}")
        
        page2.close()
    
    except Exception as e:
        print(f"❌ Error downloading this episode: {e}")
        # If a tab was opened, try to close it
        if 'page2' in locals() and not page2.is_closed():
            page2.close()


def main():
    # --- THIS IS THE ONLY PART THAT CHANGES ---
    # 1. Ask the user for the URL
    MAIN_SERIES_URL = input("Paste the thenkiri.com series URL: ")
    
    if not "thenkiri.com" in MAIN_SERIES_URL:
        print("Error: This script is only designed for thenkiri.com links.")
        return
    # --- END OF CHANGES ---

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # First, open a temporary page just to get the total count
        print("Finding all 'Download Episode' links...")
        temp_page = context.new_page()
        try:
            temp_page.goto(MAIN_SERIES_URL, timeout=60000)
        except Exception as e:
            print(f"Error: Could not load that URL. {e}")
            return
            
        episode_count = len(temp_page.get_by_text("Download Episode").all())
        print(f"Found {episode_count} episode links.")
        temp_page.close()

        # Loop from 0 up to the count
        for i in range(episode_count):
            print(f"--- Starting Episode {i+1} ---")
            
            page = None 
            try:
                page = context.new_page()
                print("Loading main page in a new tab...")
                page.goto(MAIN_SERIES_URL)
                page.wait_for_load_state()
                
                current_link_element = page.get_by_text("Download Episode").nth(i)
                
                download_episode(page, context, current_link_element)
                
                print("Waiting 10 seconds before next episode...")
                time.sleep(10) 
            
            except TimeoutError:
                print(f"❌ Failed on episode {i+1}. Hit a 'timeout' (likely rate limit).")
                print(f"Pausing script for {WAIT_TIME_ON_LIMIT / 60} minutes...")
                time.sleep(WAIT_TIME_ON_LIMIT)
                
                try:
                    print("Retrying after rate limit...")
                    if page and not page.is_closed():
                         page.close() 
                    page = context.new_page() 
                    page.goto(MAIN_SERIES_URL)
                    current_link_element = page.get_by_text("Download Episode").nth(i)
                    download_episode(page, context, current_link_element)
                except Exception as e:
                    print(f"Failed again after waiting. Skipping to next episode. Error: {e}")

            except Exception as e:
                print(f"An unexpected error occurred: {e}. Skipping to next episode.")
            
            finally:
                if page and not page.is_closed():
                    print("Closing main episode tab.")
                    page.close()

        print("🎉 All episodes downloaded!")
        browser.close()

if __name__ == "__main__":
    main()