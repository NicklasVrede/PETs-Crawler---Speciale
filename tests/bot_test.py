import asyncio
from patchright.async_api import async_playwright
import time

async def main():
    # Initialize with the async playwright
    async with async_playwright() as p:
        # Launch Firefox browser with slowMo and headful mode
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=5000,
            channel="chrome",
            
        )
        
        # Create a context with specific user agent and viewport
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        
        # Navigate to the bot detection test site
        print("Navigating to bot detection test site...")
        await page.goto("https://iphey.com/")
        
        # Wait for the page to load completely
        await page.wait_for_load_state("networkidle")
        
        print("Page loaded. Browser will remain open for 60 seconds for inspection.")
        print("Check the browser window to see test results.")
        
        # Take a screenshot
        await page.screenshot(path="edge_bot_detection_results.png")
        
        # Keep browser open for inspection
        await asyncio.sleep(60)
        
        # Close the browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
