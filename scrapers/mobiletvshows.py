# scrapers/mobiletvshows.py

import time
import os
from playwright.sync_api import TimeoutError, sync_playwright

# Rich UI imports
from rich.console import Console
from rich.theme import Theme

custom_theme = Theme({"info": "cyan", "success": "bold green", "error": "bold red", "warning": "yellow"})
console = Console(theme=custom_theme)

def save_file(download, folder_name=None):
    """Helper to save the file."""
    if folder_name:
        save_dir = os.path.join("downloads", folder_name)
        os.makedirs(save_dir, exist_ok=True)
    else:
        save_dir = "downloads"
        os.makedirs(save_dir, exist_ok=True)
        
    file_path = os.path.join(save_dir, download.suggested_filename)
    with console.status(f"[bold green]Downloading {download.suggested_filename}...[/bold green]", spinner="dots"):
        download.save_as(file_path)
    console.print(f"[success]✅ Success! File saved to:[/success] {file_path}")

def download_single_episode(context, url, folder_name=None):
    """
    Downloads a single episode from MobileTVShows.
    Uses a FRESH context to ensure downloads are allowed and not blocked by mixed content.
    """
    console.print(f"[bold cyan]🚀 Processing: {url}[/bold cyan]")
    
    # We need to spawn a new page, but ideally a new context with permissions if possible.
    # Since 'context' is passed in, we can try to use it, but if it fails we might need a fresh one.
    # For now, let's try to grab the browser from the context if possible, or just use the current context
    # and handle the download link more carefully.
    
    page = context.new_page()
    
    try:
        console.print("[dim]Loading Page...[/dim]")
        page.goto(url)
        
        # 1. Click "High MP4" / "Download This Episode" (First Page)
        console.print("[dim]📍 On Episode Page. Looking for '#dlink2'...[/dim]")
        
        try:
            # Check for potential popup/overlay first
            if page.locator("iframe").count() > 0:
                console.print("[yellow]⚠️ Pending iframes detected (potential ads)[/yellow]")

            # Attempt to click the download button
            with page.expect_popup() as popup_info:
                page.click("#dlink2", timeout=5000)
            
            # If a popup opened, it's likely an ad. Close it.
            popup = popup_info.value
            console.print(f"[yellow]Ad popup detected. Closing...[/yellow]")
            popup.close()
            
            # After closing popup, the main page often navigates or needs another click
            console.print("[dim]Waiting for navigation to 'downloadmp4.php'...[/dim]")
            try:
                page.wait_for_url("**/downloadmp4.php*", timeout=5000)
                console.print("[green]Navigation successful![/green]")
            except:
                console.print("[yellow]Page didn't auto-navigate. Clicking #dlink2 again...[/yellow]")
                page.click("#dlink2")
                page.wait_for_url("**/downloadmp4.php*")

        except Exception as e:
            # If we haven't navigated yet, try clicking again
            if "downloadmp4.php" not in page.url:
                try:
                    page.click("#dlink2", timeout=3000)
                    page.wait_for_url("**/downloadmp4.php*")
                except:
                    pass

        # 2. Final Download Page
        console.print("[dim]📍 On Download Page.[/dim]")
        
        # Helper to try downloading a link
        def try_download_link(selector, link_name):
            link = page.locator(selector)
            if link.count() > 0:
                console.print(f"[cyan]Attempting download via {selector}...[/cyan]")
                
                # Get the href
                download_href = link.get_attribute("href")
                
                # If it's relative, make it absolute
                if download_href and not download_href.startswith("http"):
                    base_url = "https://www.mobiletvshows.site/"
                    download_href = base_url + download_href
                    
                console.print(f"[dim]Target: {download_href}[/dim]")

                try:
                    # KEY FIX: filelink.php is a REDIRECT page, not a direct download
                    # We need to navigate to it and let it redirect us to the actual file
                    # THEN the download will trigger
                    
                    console.print("[dim]Navigating to redirect URL...[/dim]")
                    
                    # Expect download WHILE navigating (the redirect will trigger it)
                    with page.expect_download(timeout=60000) as download_info:
                        # Navigate directly to the filelink.php URL
                        # This will follow redirects and eventually trigger the download
                        page.goto(download_href, wait_until="commit")
                        
                    download = download_info.value
                    save_file(download, folder_name)
                    console.print(f"[green]✅ {link_name} succeeded![/green]")
                    return True
                    
                except Exception as e:
                    console.print(f"[red]{link_name} failed: {e}[/red]")
                    return False
            return False

        # Try Link 1
        if try_download_link("#flink1", "Link 1"):
            return True
            
        console.print("[yellow]Link 1 failed or missing. Switching to Link 2...[/yellow]")
        
        # Try Link 2
        if try_download_link("#flink2", "Link 2"):
            return True

        console.print("[bold red]❌ All download links failed.[/bold red]")
        console.print(f"Final Page URL: {page.url}")
        return False
        
    except Exception as e:
        console.print(f"[bold red]❌ Critical Error: {e}[/bold red]")
        return False
    finally:
        page.close()


def get_series_links(url):
    """
    Scrapes the Season Page and RETURNS a list of episode URLs.
    If given a series overview page, automatically picks the latest season.
    """
    console.print(f"[bold magenta]Scraping Series Links: {url}[/bold magenta]")
    
    with sync_playwright() as p:
        # Use a consistent User-Agent to avoid detection
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle") # Wait for network to settle
            
            # DEBUG: Check what page we're actually on
            current_url = page.url
            page_title = page.title()
            console.print(f"[dim]DEBUG - Current URL: {current_url}[/dim]")
            console.print(f"[dim]DEBUG - Page Title: {page_title}[/dim]")
            
            # 1. SERIES OVERVIEW DETECTION
            # Try to wait for EITHER episode links OR season links
            try:
                # Wait up to 3 seconds for either indicator
                page.wait_for_selector("a:has-text('High MP4'), a[itemprop='url']", timeout=3000)
            except:
                pass # Proceed to check what we found

            # Check if this is a series overview page (has season links instead of episodes)
            # We check for episodes FIRST using robust JS
            
            # DEBUG: Let's see what links are actually on the page
            all_links_sample = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.slice(0, 10).map(a => ({
                        text: a.innerText.substring(0, 50),
                        href: a.href.substring(0, 80)
                    }));
                }
            """)
            console.print(f"[dim]DEBUG - Sample links on page: {all_links_sample}[/dim]")
            
            episode_count = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.filter(a => a.innerText.toLowerCase().includes('high mp4')).length;
                }
            """)
            console.print(f"[dim]Debug: Found {episode_count} 'High MP4' links (Phase 1)[/dim]")

            if episode_count == 0:
                # No episodes found, check for seasons
                season_links = page.locator("a[itemprop='url']").all()
                
                if len(season_links) > 0:
                    console.print(f"[cyan]📺 Detected series overview page with {len(season_links)} seasons[/cyan]")
                    
                    latest_season = season_links[-1]
                    season_url = latest_season.get_attribute("href")
                    season_name = latest_season.text_content().strip()
                    
                    console.print(f"[cyan]🎬 Navigating to {season_name}...[/cyan]")
                    
                    if not season_url.startswith("http"):
                        season_url = f"https://www.mobiletvshows.site/{season_url}"
                    
                    page.goto(season_url)
                    page.wait_for_load_state("networkidle")
            
            # 2. SERIES NAME
            try:
                page_title = page.title()
                series_keyword = page_title.split('-')[0].strip()
            except:
                series_keyword = "Series"

            # 3. FINAL EPISODE SCRAPE
            # Wait for content again in case we navigated
            try:
                page.wait_for_selector("a:has-text('High MP4')", timeout=5000)
            except:
                pass # Proceed anyway

            # Use JavaScript to extract links (robust method)
            episode_data = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    // Filter for links containing 'High MP4' case-insensitive just in case
                    const highMp4Links = links.filter(a => a.innerText.toLowerCase().includes('high mp4'));
                    return highMp4Links.map(a => a.href);
                }
            """)
            
            total_eps = len(episode_data)
            console.print(f"Found [bold]{total_eps}[/bold] episodes.")

            links_data = []
            for i, href in enumerate(episode_data):
                if href:
                    # Make sure it's a full URL
                    if not href.startswith("http"):
                        full_url = f"https://www.mobiletvshows.site/{href}"
                    else:
                        full_url = href
                    
                    links_data.append({
                        "url": full_url,
                        "title": f"{series_keyword} - Ep {total_eps - i}" # Reverse index calculation
                    })
            
            # Reverse so Ep 1 is first
            links_data.reverse()
            return links_data

        except Exception as e:
            console.print(f"[error]❌ Series Scrape Failed: {e}[/error]")
            return []
        finally:
            browser.close()