from playwright.async_api import async_playwright, TimeoutError
from crawler.monitors.network_monitor import NetworkMonitor
from crawler.monitors.fingerprint_collector import FingerprintCollector
from pathlib import Path
import json
from datetime import datetime
from urllib.parse import urlparse
from tqdm import tqdm
import random
import asyncio
from utils.page_collector import load_site_pages
from utils.user_simulator import UserSimulator
import os

class WebsiteCrawler:
    def __init__(self, max_pages=20, visits=2):
        self.max_pages = max_pages
        self.visits = visits
        self.network_monitor = NetworkMonitor()
        self.fp_collector = FingerprintCollector()
        self.user_simulator = UserSimulator()
        self.base_domain = None

    async def clear_all_browser_data(self, context):
        """Clear browser data between visits"""
        print("\nClearing browser data...")
        try:
            # Clear context-level data
            print("Clearing context-level data...")
            await context.clear_cookies()
            await asyncio.sleep(1)
            await context.clear_permissions()
            await asyncio.sleep(1)
            
            # Use page-level JavaScript to clear storage with error handling
            page = context.pages[0] if context.pages else None
            if page:
                print("Clearing local and session storage...")
                try:
                    # Use a safer approach with try/catch inside the JS
                    await page.evaluate("""() => {
                        try {
                            if (window.localStorage) {
                                localStorage.clear();
                                console.log('LocalStorage cleared');
                            }
                            if (window.sessionStorage) {
                                sessionStorage.clear();
                                console.log('SessionStorage cleared');
                            }
                            return true;
                        } catch (e) {
                            console.log('Storage clearing error (expected on blank pages):', e);
                            return false;
                        }
                    }""")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Note: Could not clear page storage: {e}")
            
            print("✓ Browser data cleared")
            
        except Exception as e:
            print(f"Warning: Error during data clearing: {e}")
        
        await asyncio.sleep(1)  # Final wait before proceeding

    async def populate_cache(self, page, urls):
        """Pre-populate browser cache with resources from the target site"""
        print("\nPre-populating cache with site resources...")
        try:
            # Visit homepage first to cache common resources
            domain = self.base_domain
            await page.goto(f"https://{domain}/", timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(2000)
            
            # Quick visit to each URL to populate cache
            for url in urls[:5]:  # Visit first 5 URLs to build cache
                try:
                    await page.goto(url, timeout=20000)
                    await page.wait_for_load_state('domcontentloaded')
                except Exception as e:
                    print(f"Error pre-caching {url}: {e}")
                
            print("✓ Cache populated with site resources")
        except Exception as e:
            print(f"Error during cache population: {e}")

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
            
            #tqdm.write(f"Scrolling {int(scroll_percentage * 100)}% of page ({target_scroll}px)")
            
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

    async def _setup_browser(self, p, user_data_dir, full_extension_path, headless, viewport):
        """Setup browser with context"""
        return await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport=viewport or {'width': 1280, 'height': 800},
            args=[
                f'--disable-extensions-except={full_extension_path}',
                f'--load-extension={full_extension_path}'
            ]
        )

    async def _clear_browser_data(self, context):
        """Clear browser data"""
        await context.clear_cookies()
        await context.clear_permissions()
        
        # Use page-level JavaScript to clear storage with error handling
        page = context.pages[0] if context.pages else None
        if page:
            try:
                # Use a safer approach with try/catch inside the JS
                await page.evaluate("""() => {
                    try {
                        if (window.localStorage) {
                            localStorage.clear();
                            console.log('LocalStorage cleared');
                        }
                        if (window.sessionStorage) {
                            sessionStorage.clear();
                            console.log('SessionStorage cleared');
                        }
                        return true;
                    } catch (e) {
                        console.log('Storage clearing error (expected on blank pages):', e);
                        return false;
                    }
                }""")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Note: Could not clear page storage: {e}")

    async def crawl_site(self, domain, user_data_dir=None, full_extension_path=None, headless=False, viewport=None):
        """Crawl a website multiple times to analyze cookie persistence"""
        self.base_domain = domain.lower().replace('www.', '')
        visit_results = []
        
        # Load pre-collected URLs
        print("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages", count=self.max_pages)
        
        if not urls or len(urls) == 0:
            print(f"ERROR: No pre-collected URLs found for {domain}")
            return {'visits': [], 'fingerprinting': {}}
        
        print(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        
        # Initial browser setup - we only clear data once at the beginning
        print(f"\n{'='*50}")
        print(f"Initial browser setup")
        print(f"{'='*50}")
        
        # Clear data only once at the start of the entire crawling process
        print("\nInitial browser session to clear data and visit homepage...")
        async with async_playwright() as p:
            # Setup browser with context
            context = await self._setup_browser(
                p, user_data_dir, full_extension_path, headless, viewport
            )
            
            # Clear all browser data to start fresh
            print("\nClearing browser data...")
            await self._clear_browser_data(context)
            print("✓ Browser data cleared")
            
            # Close the context after clearing data
            await context.close()
        
        # Now perform multiple visits WITHOUT clearing data between them
        for visit in range(self.visits):
            print(f"\n{'='*50}")
            print(f"Starting visit {visit + 1} of {self.visits}")
            print(f"{'='*50}")
            
            # Browser session for this visit - data persists between visits
            print("\nStarting browser session...")
            async with async_playwright() as p:
                # Setup browser with context
                context = await self._setup_browser(
                    p, user_data_dir, full_extension_path, headless, viewport
                )
                
                # Create a new page for this visit
                page = await context.new_page()
                
                # Setup monitoring
                await self.network_monitor.setup_monitoring(page, visit)
                await self.fp_collector.setup_monitoring(page, visit)
                
                # Ensure page is ready before setting up monitor
                await page.goto("about:blank")
                

                # Visit the homepage first
                print("\nVisiting homepage...")
                homepage_url = f"https://{domain}"
                try:
                    await page.goto(homepage_url, timeout=30000)
                    await page.wait_for_timeout(5000)  # Wait for 5 seconds
                except Exception as e:
                    print(f"Error visiting homepage: {e}")
                
                # Start the crawl
                print("\nStarting URL visits...")
                visited_in_this_cycle = []
                with tqdm(total=len(urls), desc=f"Visit #{visit + 1}", unit="page") as pbar:
                    for url in urls:
                        try:
                            await page.goto(url, timeout=30000)
                            await page.wait_for_load_state('domcontentloaded')
                            await page.wait_for_timeout(random.uniform(1000, 2000))  # Random wait 1-2 seconds
                            
                            final_url = page.url
                            visited_in_this_cycle.append({"original": url, "final": final_url})
                            
                            await self.network_monitor.storage_monitor.capture_snapshot(page, visit_number=visit)
                            await self.user_simulator.simulate_interaction(page)
                            
                            pbar.update(1)
                            
                        except Exception as e:
                            print(f"\nError visiting {url}: {e}")
                            visited_in_this_cycle.append({"original": url, "error": str(e)})
                            pbar.update(1)
                
                visit_results.append({
                    'visit_number': visit,
                    'network': self.network_monitor.get_results()['network_data'],
                    'statistics': self.network_monitor.get_statistics(),
                    'fingerprinting': self.fp_collector._get_results_for_visit(visit),
                    'visited_urls': visited_in_this_cycle
                })
                
                # Before closing the page, collect storage interactions again
                await self.network_monitor.storage_monitor.collect_storage_interactions(page, visit)
                
                # Close the context at the end of this visit
                await context.close()
        
        # Remove the cookie persistence analysis - we'll do this separately
        return {
            'visits': visit_results,
            'fingerprinting_summary': self.fp_collector._get_combined_results()
        }