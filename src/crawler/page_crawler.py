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
        self.base_domain = None

    async def clear_browser_data(self, context):
        """Clear all browser storage data including cookies and local storage"""
        try:
            # Get the active page
            page = context.pages[0]
            
            # Clear cookies and storage at browser level
            await context.clear_cookies()
            await context.clear_permissions()
            
            # Clear page-level storage with error handling
            await page.evaluate("""() => {
                try {
                    // Clear localStorage if accessible
                    try { localStorage.clear(); } catch (e) { console.log("localStorage not accessible"); }
                    
                    // Clear sessionStorage if accessible
                    try { sessionStorage.clear(); } catch (e) { console.log("sessionStorage not accessible"); }
                    
                    // Clear cookies with error handling
                    try {
                        document.cookie.split(";").forEach(c => { 
                            const domain = window.location.hostname;
                            if (domain) {
                                const name = c.split("=")[0].trim();
                                document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${domain}`;
                                document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${domain}`;
                            }
                        });
                    } catch (e) { console.log("Cookie clearing not accessible"); }
                    
                    // Clear IndexedDB if accessible
                    try {
                        indexedDB.databases().then(dbs => {
                            dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                        });
                    } catch (e) { console.log("IndexedDB not accessible"); }
                } catch (e) {
                    console.log("Storage clearing error:", e);
                }
            }""")
            
            # Try to clear browser cache using CDP if available
            try:
                client = await page.context.new_cdp_session(page)
                await client.send('Network.clearBrowserCache')
                await client.send('Network.clearBrowserCookies')
            except Exception as e:
                tqdm.write(f"CDP clearing not available: {str(e)}")
            
        except Exception as e:
            tqdm.write(f"Warning: Could not clear all browser data: {str(e)}")

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
        """Simulate natural user behavior on the page with shorter, more variable scrolling"""
        try:
            # Brief initial wait
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Get total scroll height and start scrolling quickly
            max_scroll = await page.evaluate('document.body.scrollHeight')
            scroll_amount = 0
            
            # Variable scroll depth strategy
            current_url = page.url
            
            # Extract domain for homepage check if we have it
            parsed_url = urlparse(current_url)
            current_domain = parsed_url.netloc.lower().replace('www.', '')
            
            deep_scroll_chance = 0.1  # 10% chance for deep scroll
            is_homepage = self.base_domain and current_domain == self.base_domain and parsed_url.path in ['/', '']
            
            if is_homepage:
                # More thorough for homepage
                scroll_percentage = random.uniform(0.3, 0.8)
            elif random.random() < deep_scroll_chance:
                # Occasional deep scroll
                scroll_percentage = random.uniform(0.5, 1.0)
            else:
                # Default quick scroll for most pages
                scroll_percentage = random.uniform(0.1, 0.4)
            
            target_scroll = int(max_scroll * scroll_percentage)
            
            tqdm.write(f"Scrolling {int(scroll_percentage * 100)}% of page ({target_scroll}px)")
            
            # Get viewport dimensions
            viewport = page.viewport_size
            middle_x = viewport['width'] // 2
            middle_y = viewport['height'] // 2
            
            # Quick mouse movement
            await page.mouse.move(middle_x, middle_y, steps=2)
            
            # Faster scrolling with fewer pauses
            scroll_speeds = ['fast', 'medium', 'slow']
            scroll_probabilities = [0.7, 0.2, 0.1]
            scroll_speed = random.choices(scroll_speeds, weights=scroll_probabilities, k=1)[0]
            
            # Adjust scroll parameters based on speed
            if scroll_speed == 'fast':
                scroll_increment = random.randint(100, 200)
                scroll_pause = 0.05
            elif scroll_speed == 'medium':
                scroll_increment = random.randint(50, 100)
                scroll_pause = 0.1
            else:  # slow
                scroll_increment = random.randint(30, 60)
                scroll_pause = 0.2
            
            # Scroll down
            while scroll_amount < target_scroll:
                # Calculate next scroll increment
                next_increment = min(scroll_increment, target_scroll - scroll_amount)
                if next_increment <= 0:
                    break
                    
                # Scroll
                await page.mouse.wheel(0, next_increment)
                scroll_amount += next_increment
                
                # Brief pause
                await asyncio.sleep(scroll_pause)
                
                # Occasionally move mouse
                if random.random() > 0.85:
                    await page.mouse.move(
                        middle_x + random.randint(-200, 200),
                        middle_y + random.randint(-100, 100),
                        steps=2
                    )
            
            # Brief pause at end
            await asyncio.sleep(0.1)
            
            # Only 20% chance to scroll back to top (saves time)
            if random.random() < 0.2:
                await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
                await asyncio.sleep(0.2)
            
        except Exception as e:
            tqdm.write(f"Scroll error: {str(e)}")

    async def crawl_site(self, domain, user_data_dir, full_extension_path, headless=False, viewport=None):
        """Crawl a website and collect data using a specified browser executable."""
        # Set base_domain for use in other methods
        self.base_domain = domain.lower().replace('www.', '')
        
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
                
                # Clear data only once at the start
                await self.clear_browser_data(browser)
                
                # Visit and scroll homepage first (index 0)
                homepage = f"https://{domain}"
                tqdm.write(f"\nVisiting homepage (index 0): {homepage}")
                await page.goto(homepage, timeout=60000)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Set page index for homepage
                await page.evaluate("window.currentPageIndex = 0;")
                
                tqdm.write("Starting homepage interaction...")
                await self.simulate_user_interaction(page)
                tqdm.write("Finished homepage interaction")
                
                # Now extract links directly without visiting subpages yet
                extractor = LinkExtractor(domain)
                
                # First extract from homepage (we already did some interaction)
                homepage_links = await extractor.extract_links(page)
                
                # Now try clicking menus and navigation to expose more links
                # Common navigation trigger selectors
                nav_triggers = [
                    '.menu-toggle', '.navbar-toggle', '.menu-icon', '.nav-toggle',
                    '.hamburger', '[data-toggle="collapse"]', '.mobile-nav-toggle',
                    '#menu-button', '.navigation-trigger', '.menu-trigger',
                    'button[aria-label*="menu"]', 'button[aria-label*="navigation"]'
                ]
                
                tqdm.write("Trying to open navigation menus to find more links...")
                for selector in nav_triggers:
                    try:
                        count = await page.locator(selector).count()
                        if count > 0:
                            tqdm.write(f"Found menu trigger: {selector}")
                            await page.locator(selector).first.click()
                            await asyncio.sleep(1)  # Wait for menu to expand
                            more_links = await extractor.extract_links(page)
                            tqdm.write(f"Found {len(more_links)} additional links after clicking {selector}")
                            homepage_links.update(more_links)
                    except Exception as e:
                        continue
                
                # Complete subpage extraction
                urls = await extractor.get_subpages(page, self.max_pages)
                
                with tqdm(total=len(urls), desc=f"Crawling {domain}", unit="page") as pbar:
                    for index, url in enumerate(urls, start=1):  # Start from 1 since homepage is 0
                        try:
                            if url != homepage:  # Skip homepage since we already visited it
                                tqdm.write(f"\nVisiting (index {index}): {url}")
                                await page.goto(url, timeout=60000)
                                
                                # Set page index for current page
                                await page.evaluate(f"window.currentPageIndex = {index};")
                                
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