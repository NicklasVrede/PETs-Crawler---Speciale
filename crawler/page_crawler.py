import asyncio
from playwright.async_api import async_playwright

class WebsiteCrawler:
    async def crawl_site(self, domain, user_data_dir, full_extension_path=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir,
                **browser_args # Assuming browser_args is defined earlier
            )

            # Wait a brief moment for any extension tabs to potentially open
            await asyncio.sleep(2) # Adjust sleep time if needed

            pages = browser.pages
            if self.verbose:
                print(f"Initial pages count: {len(pages)}")
                for i, p in enumerate(pages):
                    print(f"  Page {i}: {p.url}")

            # Close extra tabs opened by the extension (often the first one)
            # Keep only the last opened page, assuming it's the main one,
            # or create a new one if needed.
            initial_page_count = len(pages)
            target_page = None

            if initial_page_count > 1:
                if self.verbose:
                    print(f"Closing {initial_page_count - 1} extra initial tab(s).")
                # Iterate backwards to avoid index issues when closing
                for i in range(initial_page_count - 1, 0, -1):
                     # Simple strategy: close all but the last page.
                     # More robust: check URLs (e.g., 'chrome-extension://', 'about:blank')
                     # and keep the one that isn't an extension page, or the last one.
                     page_to_close = pages[i-1]
                     if "chrome-extension://" in page_to_close.url or page_to_close.url == "about:blank":
                         if self.verbose:
                             print(f"Closing page {i-1}: {page_to_close.url}")
                         await page_to_close.close()
                     # Update the pages list reference if needed, though Playwright might handle this
                     pages = browser.pages # Refresh pages list

                # Use the remaining page (should be the last one opened, or the first if others closed)
                if browser.pages:
                    target_page = browser.pages[0]
                else:
                    # If all pages were closed somehow, create a new one
                    if self.verbose:
                        print("All initial pages closed, creating a new one.")
                    target_page = await browser.new_page()

            elif initial_page_count == 1:
                # If only one page, use it
                target_page = pages[0]
                # Optional: Check if it's an extension page and navigate away or create new
                if "chrome-extension://" in target_page.url:
                     if self.verbose:
                         print(f"Initial page is an extension page: {target_page.url}. Creating a new page for navigation.")
                     # Close the extension page and create a new one
                     await target_page.close()
                     target_page = await browser.new_page()
                     # Or alternatively, navigate the existing page:
                     # await target_page.goto("about:blank") # Navigate away first

            else: # No pages initially (unlikely but possible)
                if self.verbose:
                    print("No initial pages found, creating a new one.")
                target_page = await browser.new_page()

            if self.verbose:
                 print(f"Using page: {target_page.url if target_page else 'None'}")
                 print(f"Current page count: {len(browser.pages)}")

            # Ensure we have a valid page to work with
            if not target_page:
                 print("Error: Could not establish a target page.")
                 await browser.close()
                 return None # Or raise an exception

            # Proceed with crawling using 'target_page' instead of 'page'
            target_url = f"https://{domain}" # Use https or http as appropriate
            if self.verbose:
                print(f"Navigating to {target_url}...")

            try:
                await target_page.goto(target_url, wait_until='domcontentloaded', timeout=60000) # Added timeout
                # ... rest of the crawling logic using target_page ...

            except Exception as e:
                print(f"Error navigating to {target_url} or during crawl: {e}")
                # Handle error appropriately
            finally:
                 if self.verbose:
                     print("Closing browser context...")
                 await browser.close()

            return # ... crawl results ... 