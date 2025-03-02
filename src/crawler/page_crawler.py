from playwright.async_api import async_playwright, TimeoutError
from crawler.link_extractor import LinkExtractor
from crawler.monitors.network_monitor import NetworkMonitor
from crawler.monitors.fingerprint_collector import FingerprintCollector
from pathlib import Path
import json
from datetime import datetime
from urllib.parse import urlparse
from tqdm import tqdm
import random
import asyncio

class WebsiteCrawler:
    def __init__(self, max_pages=20):
        self.max_pages = max_pages
        self.network_monitor = NetworkMonitor()
        self.fp_collector = FingerprintCollector()
        self.cache_populated = False

    async def clear_browser_data(self, context):
        """Clear all browser storage data including cookies and local storage"""
        # Clear cookies from context
        await context.clear_cookies()
        
        # Get existing pages
        pages = context.pages
        if not pages:
            # Create a new page if none exists
            page = await context.new_page()
        else:
            page = pages[0]
        
        try:
            # Try to clear storage, but don't fail if we can't
            await page.evaluate("""() => {
                try {
                    localStorage.clear();
                    sessionStorage.clear();
                } catch (e) {
                    // Ignore errors if storage isn't accessible
                    console.log('Could not clear storage:', e);
                }
            }""")
        except Exception as e:
            print(f"Note: Could not clear browser storage: {str(e)}")

    async def populate_cache(self, domain, user_data_dir, full_extension_path, headless, viewport):
        """Pre-populate browser cache with initial page load"""
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    viewport=viewport or {'width': 1280, 'height': 800},
                    args=[
                        f'--disable-extensions-except={full_extension_path}',
                        f'--load-extension={full_extension_path}'
                    ]
                )
                page = browser.pages[0]
                
                # Increase timeouts and wait for key events
                await page.goto(f"https://{domain}", timeout=30000)  # 30 seconds
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                self.cache_populated = True
                await browser.close()
                
            except Exception as e:
                print(f"Cache population warning for {domain}: {str(e)}")
                # Continue even if cache population fails
                self.cache_populated = True

    async def simulate_user_interaction(self, page):
        """Simulate natural user behavior on the page using smooth mouse wheel scrolling"""
        try:
            # Get total scroll height
            max_scroll = await page.evaluate('document.body.scrollHeight')
            scroll_amount = 0
            
            # Randomly decide how much of the page to scroll (50-100%)
            scroll_percentage = random.uniform(0.5, 1.0)
            target_scroll = int(max_scroll * scroll_percentage)
            
            tqdm.write(f"\nScrolling {int(scroll_percentage * 100)}% of page height: {target_scroll}px")
            
            # Get viewport dimensions
            viewport = page.viewport_size
            middle_x = viewport['width'] // 2
            middle_y = viewport['height'] // 2
            
            # Move mouse to middle of viewport
            await page.mouse.move(middle_x, middle_y)
            
            # Scroll down with smooth acceleration and deceleration
            while scroll_amount < target_scroll:
                # Use smaller, more frequent wheel deltas for smoother scrolling
                # Simulate touchpad-like smooth scroll
                for _ in range(5):  # Bundle multiple small scrolls together
                    delta_y = random.randint(30, 50)  # Smaller increments
                    await page.mouse.wheel(0, delta_y)
                    scroll_amount += delta_y
                    await asyncio.sleep(0.016)  # ~60fps for smooth animation
                
                # Move mouse smoothly and naturally
                if random.random() > 0.7:  # 30% chance to move mouse
                    await page.mouse.move(
                        middle_x + random.randint(-200, 200),
                        middle_y + random.randint(-100, 100),
                        steps=5  # Smooth mouse movement
                    )
                
                # Brief pause between scroll bundles
                await asyncio.sleep(random.uniform(0.1, 0.2))
                
                # Occasional longer pause (5% chance)
                if random.random() > 0.95:
                    await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # Short pause at current position
            await asyncio.sleep(0.3)
            
            # 50% chance to scroll back to top
            if random.random() > 0.5:
                await page.evaluate("""
                    window.scrollTo({
                        top: 0,
                        behavior: 'smooth'
                    });
                """)
            
        except Exception as e:
            tqdm.write(f"Scroll error: {str(e)}")

    async def crawl_site(self, domain, user_data_dir, full_extension_path, headless=False, viewport=None):
        """Crawl a website and collect data using a specified browser executable."""
        if not self.cache_populated:
            await self.populate_cache(domain, user_data_dir, full_extension_path, headless, viewport)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport=viewport or {'width': 1280, 'height': 800},
                args=[
                    f'--disable-extensions-except={full_extension_path}',
                    f'--load-extension={full_extension_path}'
                ]
            )

            try:
                page = browser.pages[0]
                await self.network_monitor.setup_monitoring(page)
                await self.fp_collector.setup_monitoring(page)
                
                # Visit and scroll homepage first
                homepage = f"https://{domain}"
                tqdm.write(f"\nVisiting homepage: {homepage}")
                await page.goto(homepage, timeout=60000)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                tqdm.write("Starting homepage interaction...")
                await self.simulate_user_interaction(page)
                tqdm.write("Finished homepage interaction")
                
                # Now get and visit subpages
                extractor = LinkExtractor(domain)
                urls = await extractor.get_subpages(page, self.max_pages)
                
                with tqdm(total=len(urls), desc=f"Crawling {domain}", unit="page") as pbar:
                    for url in urls:
                        try:
                            if url != homepage:  # Skip homepage since we already visited it
                                tqdm.write(f"\nVisiting: {url}")
                                await page.goto(url, timeout=60000)
                                
                                try:
                                    await page.wait_for_load_state('domcontentloaded', timeout=30000)
                                    try:
                                        await page.wait_for_load_state('networkidle', timeout=10000)
                                    except TimeoutError:
                                        tqdm.write("Network idle timeout - continuing anyway")
                                    
                                    tqdm.write("Starting page interaction...")
                                    await self.simulate_user_interaction(page)
                                    tqdm.write("Finished page interaction")
                                    
                                except TimeoutError as e:
                                    tqdm.write(f"Page load timeout - attempting scroll anyway: {str(e)}")
                                    await self.simulate_user_interaction(page)
                            
                            pbar.update(1)
                            
                        except Exception as e:
                            tqdm.write(f"Error on page {url}: {str(e)}")
                            continue
                
                return {
                    'fingerprinting': self.fp_collector.get_fingerprinting_results(),
                    'network': self.network_monitor.get_results()
                }
                
            finally:
                await browser.close()