# scrapers/animepahe.py

import time
import os
from playwright.sync_api import TimeoutError

# We need to define the hosts specific to this scraper
PAHE_HOSTS = ["animepahe.si", "pahe.win", "kwik.cx"]

def save_file(download):
    """Helper to save the file."""
    file_path = os.path.join("downloads", download.suggested_filename)
    print(f"⬇️ Saving to {file_path}...")
    download.save_as(file_path)
    print(f"✅ Success! File saved.")

def handle_kwik_page(page):
    """
    Handles the final Kwik.cx download page.
    Kwik is tricky: It often requires a specific button click or waiting for JS.
    """
    print("⚠️ Landed on Kwik.cx! Attempting to bypass...")
    
    try:
        # Kwik usually has a specific download form or button.
        # We look for a button that likely contains "Download"
        # Sometimes it's an input type="submit" inside a form
        
        # Wait for the page to fully load its scripts
        page.wait_for_load_state('networkidle')
        
        # Try 1: Generic "Download" text
        try:
            with page.expect_download(timeout=10000) as download_info:
                page.get_by_text("Download", exact=False).first.click()
            return download_info.value
        except:
            print("Generic 'Download' text failed. Trying form submission...")

        # Try 2: The specific Kwik form button (often inside a <form>)
        # This selector finds a button inside a form
        try:
            with page.expect_download(timeout=10000) as download_info:
                page.locator("form button").first.click()
            return download_info.value
        except:
            pass

        raise Exception("Could not trigger download on Kwik.")

    except Exception as e:
        print(f"❌ Kwik Bypass Failed: {e}")
        raise e

def download_single_episode(context, url):
    """
    Downloads a SINGLE episode from an AnimePahe /play/ URL.
    """
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    page = context.new_page()
    try:
        print(f"Loading AnimePahe Play Page: {url}")
        page.goto(url)
        page.wait_for_load_state()

        # 1. Find and Click the "Download" Menu
        # Note: You might need to adjust this text if the button has no text
        print("Looking for Download menu...")
        page.get_by_text("Download", exact=False).click()
        
        # 2. Select Resolution (We default to 720p, or fall back to 1080p)
        print("Menu opened. Looking for resolution links...")
        
        # We try to find a link containing "720p" (usually the sweet spot for AnimePahe)
        # Note: These open in a new tab (Ad/Redirect)
        res_link = page.get_by_text("720p", exact=False).first
        if not res_link.is_visible():
            print("720p not found, trying 1080p...")
            res_link = page.get_by_text("1080p", exact=False).first
            
        if not res_link.is_visible():
            raise Exception("Could not find any resolution links (720p/1080p).")

        print("Clicking resolution link...")
        
        # This click triggers the redirect chain
        with page.expect_popup() as popup_info:
            res_link.click()
        
        ad_page = popup_info.value
        ad_page.wait_for_load_state()
        print(f"Redirected to: {ad_page.url}")

        # 3. Navigate the Redirect Chain (Pahe.win -> Kwik)
        # Sometimes it goes straight to Kwik, sometimes it has an intermediate page
        # We wait and see if we land on Kwik
        
        final_download_object = None
        
        # We give it 15 seconds to settle on the final domain
        for _ in range(15):
            if "kwik" in ad_page.url:
                print("We are on Kwik!")
                final_download_object = handle_kwik_page(ad_page)
                break
            elif "pahe" in ad_page.url:
                print("On intermediate ad page... waiting for redirect...")
                # Sometimes you have to click "Continue" on the ad page
                try:
                    ad_page.get_by_text("Continue", exact=False).click(timeout=2000)
                except:
                    pass
            time.sleep(1)
            
        if final_download_object:
            save_file(final_download_object)
        else:
            print("❌ Failed to reach Kwik or start download.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        page.close()