# scrapers/animepahe.py

import time
import os
from playwright.sync_api import TimeoutError

# Rich UI imports
from rich.console import Console
from rich.theme import Theme

custom_theme = Theme({"info": "cyan", "success": "bold green", "error": "bold red", "warning": "yellow"})
console = Console(theme=custom_theme)

def save_file(download):
    """Helper to save the file."""
    file_path = os.path.join("downloads", download.suggested_filename)
    with console.status(f"[bold green]Downloading {download.suggested_filename}...[/bold green]", spinner="dots"):
        download.save_as(file_path)
    console.print(f"[success]✅ Success! File saved to:[/success] {file_path}")

def handle_kwik_page(page):
    """
    Handles the final Kwik.cx download page.
    """
    console.print("[info]⚠️ Landed on Kwik.cx! Attempting to bypass...[/info]")
    
    try:
        page.wait_for_load_state('networkidle')
        
        # STRATEGY 1: Look for the specific download form button
        try:
            console.print("Attempting Kwik Strategy 1 (Form Button)...")
            with page.expect_download(timeout=10000) as download_info:
                page.locator("form button").first.click()
            return download_info.value
        except:
            pass

        # STRATEGY 2: Look for generic "Download" text
        try:
            console.print("Attempting Kwik Strategy 2 (Text Match)...")
            with page.expect_download(timeout=10000) as download_info:
                page.get_by_text("Download", exact=False).first.click()
            return download_info.value
        except:
            pass
        
        raise Exception("All Kwik bypass strategies failed.")

    except Exception as e:
        console.print(f"[error]❌ Kwik Bypass Failed: {e}[/error]")
        raise e

def download_single_episode(context, url):
    """
    Downloads a SINGLE episode from an AnimePahe /play/ URL.
    """
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    page = context.new_page()
    try:
        console.print(f"[info]Loading AnimePahe Play Page...[/info]")
        page.goto(url)
        page.wait_for_load_state()

        # 1. Click the "Download" Menu to reveal options
        console.print("Opening Download Menu...")
        try:
            page.get_by_text("Download", exact=False).click()
            # Wait for the menu to animate in
            page.wait_for_timeout(1000) 
        except Exception as e:
            console.print(f"[warning]Menu issue: {e}. Checking if items are already visible...[/warning]")

        # 2. Find the Resolution Link
        console.print("Looking for resolution links...")
        
        # FIX: We only look for 'a' tags (links), ignoring 'button' tags
        # This prevents it from clicking "kwik" or "Episode 1"
        all_links = page.locator("a.dropdown-item")
        
        # Debug print to show what LINKS we found (not buttons)
        console.print(f"[dim]Found {all_links.count()} potential download links.[/dim]")

        # PREFERENCE LOGIC: Try 720p first, then 1080p
        res_link = all_links.filter(has_text="720p").first
        
        if not res_link.is_visible():
            console.print("[warning]720p not found, trying 1080p...[/warning]")
            res_link = all_links.filter(has_text="1080p").first
            
        if not res_link.is_visible():
            # Fallback: Just pick the FIRST link (not button) available
            if all_links.count() > 0:
                 console.print("[warning]Specific res not found. Picking first link...[/warning]")
                 res_link = all_links.first
            else:
                raise Exception("Could not find any actual download links.")

        res_text = res_link.text_content().strip()
        console.print(f"Selected Resolution: [bold]{res_text}[/bold]")
        
        # 3. Click and Handle the Popup
        # We use force=True in case the menu is slightly covered
        with page.expect_popup() as popup_info:
            res_link.click(force=True)
        
        ad_page = popup_info.value
        console.print(f"Redirected to: [dim]{ad_page.url}[/dim]")
        
        # 4. Navigate the Redirect Chain (Pahe.win -> Kwik)
        final_download_object = None
        
        console.print("Waiting for Kwik.cx redirection...")
        for _ in range(20):
            try:
                current_url = ad_page.url
                if "kwik" in current_url:
                    final_download_object = handle_kwik_page(ad_page)
                    break
                elif "pahe.win" in current_url:
                    try:
                        ad_page.get_by_text("Continue", exact=False).click(timeout=1000)
                    except:
                        pass
            except:
                pass
            time.sleep(1)
            
        if final_download_object:
            save_file(final_download_object)
        else:
            console.print("[error]❌ Failed to reach Kwik or start download.[/error]")
            if not ad_page.is_closed(): ad_page.close()

    except Exception as e:
        console.print(f"[error]❌ Error: {e}[/error]")
    finally:
        if not page.is_closed(): page.close()