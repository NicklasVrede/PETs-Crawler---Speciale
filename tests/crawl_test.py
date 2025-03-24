import asyncio
from rebrowser_playwright.async_api import async_playwright
from playwright_stealth import Stealth
import time

async def main():
    # Initialize stealth with the async playwright
    async with Stealth().use_async(async_playwright()) as p:
        # Launch browser with slowMo and headful mode
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=5000  # 500ms delay between actions
        )
        
        # Create a context and page
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # Navigate to the bot detection test site
        print("Navigating to bot detection test site...")
        await page.goto("https://bot-detector.rebrowser.net/")
        
        # Wait for the page to load completely
        await page.wait_for_load_state("networkidle")
        
        print("Page loaded. Browser will remain open for 60 seconds for inspection.")
        print("Check the browser window to see test results.")
        
        # Take a screenshot
        await page.screenshot(path="bot_detection_results.png")
        
        # Keep browser open for inspection
        await asyncio.sleep(60)
        
        # Close the browser
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
