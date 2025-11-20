# scrapers/nkiri.py

import time
import os
from playwright.sync_api import TimeoutError
from config import DOWNLOAD_HOSTS

# --- RICH UI IMPORTS ---
from rich.console import Console
from rich.status import Status
from rich.theme import Theme

# Custom theme for the console
custom_theme = Theme({
    "info": "cyan",
    "success": "bold green",
    "error": "bold red",
    "warning": "yellow"
})
console = Console(theme=custom_theme)
# -----------------------

WAIT_TIME_ON_LIMIT = 900 

def save_file(download):
    """Helper to save the downloaded file with a visual spinner."""
    file_path = os.path.join("downloads", download.suggested_filename)
    
    # The Spinner Animation
    with console.status(f"[bold green]Downloading {download.suggested_filename}... (This may take a while)", spinner="dots"):
        download.save_as(file_path)

    console.print(f"[success]✅ Success![/success] File saved to: [underline]{file_path}[/underline]")

def download_episode(page, context, download_link_element):
    """
    Core automation logic with Rich UI updates.
    """
    try:
        console.print("[info]Clicking 'Download Episode' link...[/info]")
        download_link_element.click()
        
        page2 = None
        console.print("Waiting for download host tab to appear...", style="dim")

        # Poll for 10 seconds to find the new tab
        for _ in range(10): 
            all_pages = context.pages
            found = False
            for p in all_pages:
                if any(host in p.url for host in DOWNLOAD_HOSTS):
                    page2 = p
                    found = True
                    break 
            if found:
                break 
            time.sleep(1) 

        if not page2:
            console.print("❌ [error]Error:[/error] Could not find the download host page.")
            for p in context.pages:
                if p != page and "thenkiri.com" not in p.url:
                    if not p.is_closed(): p.close()
            return 

        console.print(f"Switched to correct tab: [blue]{page2.url}[/blue]")
        page2.bring_to_front()

        # Close ads
        for p in context.pages:
            if p != page and p != page2: 
                if not p.is_closed(): p.close()
        
        page2.wait_for_load_state()

        # --- ADAPTIVE DOWNLOAD LOGIC ---
        console.print("Looking for 'Create download link'...")
        try:
            page2.wait_for_load_state()
            try:
                with page2.expect_download(timeout=5000) as download_info_1:
                    page2.get_by_text("Create download link").click()
                
                console.print("[success]2-Step Flow detected:[/success] Download started.")
                save_file(download_info_1.value)
                page2.close()
                return

            except TimeoutError:
                pass
            except Exception:
                pass

        except Exception as e:
            console.print(f"[warning]Could not click 'Create download link': {e}[/warning]")

        # --- STEP 2 ---
        console.print("Checking for 'Start download' button (Step 2)...")
        try:
            start_btn = page2.locator("#direct_link").or_(page2.get_by_text("Start download"))
            start_btn.wait_for(state="visible", timeout=10000)
            
            console.print("Clicking 'Start download'...")
            with page2.expect_download(timeout=30000) as download_info_2:
                start_btn.click()
            
            console.print("[success]3-Step Flow detected:[/success] Download started.")
            save_file(download_info_2.value)
            page2.close()
            return

        except Exception as e:
            console.print(f"[error]❌ Error finding/clicking final button: {e}[/error]")
            page2.close()

    except Exception as e:
        console.print(f"[error]❌ Error downloading this episode: {e}[/error]")
        if 'page2' in locals() and not page2.is_closed():
            page2.close()

def download_series(context, url):
    """
    The main driver function for the nkiri.com scraper.
    """
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # 1. SMART EXTRACT SERIES NAME FROM URL
    try:
        # Get the full slug part (e.g. "the-mighty-nein-s01-...")
        full_slug = url.rstrip('/').split('/')[-1].lower()
        parts = full_slug.split('-')
        
        # Default to the first word
        series_slug = parts[0]
        
        # If the first word is a generic stop word, use the second word instead
        if series_slug in ['the', 'a', 'an'] and len(parts) > 1:
            series_slug = parts[1]
            
        console.print(f"🔎 Series Keyword identified: [bold cyan]'{series_slug}'[/bold cyan]")
    except:
        series_slug = ""

    temp_page = context.new_page()
    try:
        temp_page.goto(url, timeout=60000)
    except Exception as e:
        console.print(f"[error]Error: Could not load that URL. {e}[/error]")
        return
        
    episode_count = len(temp_page.get_by_text("Download Episode").all())
    console.print(f"Found [bold]{episode_count}[/bold] episode links.")
    temp_page.close()

    VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.mov']
    existing_files = [f for f in os.listdir("downloads") if os.path.splitext(f)[1] in VIDEO_EXTENSIONS]

    for i in range(episode_count):
        ep_num = i + 1
        ep_tag_variants = [f"E{ep_num:02d}", f"Episode {ep_num}"]

        already_downloaded = False
        for filename in existing_files:
            # Check if the filename actually belongs to THIS series
            if series_slug and series_slug not in filename.lower():
                continue 
            
            # Check if the episode number matches
            if any(tag in filename for tag in ep_tag_variants):
                already_downloaded = True
                break
        
        if already_downloaded:
            console.print(f"⏩ [dim]Skipping Episode {i + 1}. File found for '{series_slug}'.[/dim]")
            time.sleep(0.2)
            continue 
        
        console.rule(f"[bold]Starting Episode {i+1}[/bold]")
        
        page = None 
        try:
            page = context.new_page()
            console.print("Loading main page in a new tab...", style="dim")
            page.goto(url)
            page.wait_for_load_state()
            
            current_link_element = page.get_by_text("Download Episode").nth(i)
            download_episode(page, context, current_link_element)
            
            console.print("Waiting 10 seconds before next episode...", style="dim")
            time.sleep(10) 
        
        except TimeoutError:
            console.print(f"[error]❌ Failed on episode {i+1}. Hit a 'timeout' (likely rate limit).[/error]")
            console.print(f"Pausing script for {WAIT_TIME_ON_LIMIT / 60} minutes...")
            time.sleep(WAIT_TIME_ON_LIMIT)
            
            console.print("[warning]Retrying after rate limit...[/warning]")
            try:
                if page and not page.is_closed(): page.close()
                page = context.new_page() 
                page.goto(url)
                current_link_element = page.get_by_text("Download Episode").nth(i)
                download_episode(page, context, current_link_element)
            except Exception as e:
                console.print(f"[error]Failed again. Skipping. Error: {e}[/error]")

        except Exception as e:
            console.print(f"[error]An unexpected error occurred: {e}.[/error]")
        
        finally:
            if page and not page.is_closed():
                page.close()

    console.print("[bold green]🎉 --- NKIRI SCRAPE FINISHED --- 🎉[/bold green]")
    return True