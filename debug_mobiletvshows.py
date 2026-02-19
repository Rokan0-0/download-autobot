from playwright.sync_api import sync_playwright

url = "https://www.mobiletvshows.site/files-Supernatural--16391.htm"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print(f"Navigating to: {url}")
    page.goto(url)
    page.wait_for_load_state()
    
    # Check for different selectors
    print("\n=== Checking different selectors ===")
    
    # Original selector
    selector1 = "a:has(small:text('(High MP4)'))"
    count1 = page.locator(selector1).count()
    print(f"1. {selector1}: {count1} found")
    
    # Try without small tag
    selector2 = "a:text('High MP4')"
    count2 = page.locator(selector2).count()
    print(f"2. {selector2}: {count2} found")
    
    # Try with contains
    selector3 = "a:has-text('High MP4')"
    count3 = page.locator(selector3).count()
    print(f"3. {selector3}: {count3} found")
    
    # Get all links and filter
    all_links = page.locator("a").all()
    high_mp4_links = []
    for link in all_links:
        text = link.text_content()
        if text and "High MP4" in text:
            high_mp4_links.append(link)
            href = link.get_attribute("href")
            print(f"   Found: {text[:50]}... -> {href}")
    
    print(f"\n4. Manual filter: {len(high_mp4_links)} found")
    
    # Check page title
    print(f"\nPage title: {page.title()}")
    
    input("\nPress Enter to close browser...")
    browser.close()
