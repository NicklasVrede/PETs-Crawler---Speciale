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
    def __init__(self, max_pages=20, visits=2):
        self.max_pages = max_pages
        self.visits = visits
        self.network_monitor = NetworkMonitor()
        self.fp_collector = FingerprintCollector()
        self.base_domain = None

    async def clear_all_browser_data(self, browser):
        """Clear ALL browser data at startup"""
        try:
            page = browser.pages[0]
            
            # Clear browser-level data
            await browser.clear_cookies()
            await browser.clear_permissions()
            
            # Clear ALL storage data
            await page.evaluate("""() => {
                try {
                    // Clear localStorage
                    localStorage.clear();
                    
                    // Clear sessionStorage
                    sessionStorage.clear();
                    
                    // Clear cookies
                    document.cookie.split(";").forEach(c => {
                        const domain = window.location.hostname;
                        if (domain) {
                            const name = c.split("=")[0].trim();
                            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${domain}`;
                            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${domain}`;
                        }
                    });
                    
                    // Clear IndexedDB
                    indexedDB.databases().then(dbs => {
                        dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                    });
                    
                    // Clear Cache Storage
                    if ('caches' in window) {
                        caches.keys().then(keys => {
                            keys.forEach(key => caches.delete(key));
                        });
                    }
                    
                    // Clear Service Workers
                    if ('serviceWorker' in navigator) {
                        navigator.serviceWorker.getRegistrations().then(registrations => {
                            registrations.forEach(registration => registration.unregister());
                        });
                    }
                    
                } catch (e) {
                    console.log("Error clearing data:", e);
                }
            }""")
            
            print("Successfully cleared all browser data at startup")
            
        except Exception as e:
            print(f"Error during initial data clearing: {e}")

    async def clear_browser_data(self, browser):
        """Selectively clear data between visits"""
        try:
            # Get the active page
            page = browser.pages[0]
            
            # Clear only session-related data
            await page.evaluate("""() => {
                try {
                    // Clear sessionStorage
                    try { 
                        sessionStorage.clear(); 
                    } catch (e) { 
                        console.log("sessionStorage not accessible"); 
                    }
                    
                    // Clear session cookies only (keep persistent cookies)
                    try {
                        document.cookie.split(";").forEach(c => { 
                            const cookie = c.trim();
                            // Check if cookie has no expiry (session cookie)
                            if (!cookie.toLowerCase().includes('expires=') && 
                                !cookie.toLowerCase().includes('max-age=')) {
                                const name = cookie.split("=")[0];
                                const domain = window.location.hostname;
                                document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${domain}`;
                                document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${domain}`;
                            }
                        });
                    } catch (e) { 
                        console.log("Cookie clearing not accessible"); 
                    }
                    
                } catch (e) {
                    console.log("Storage clearing error:", e);
                }
            }""")
            
            # Clear browser cache but keep cookies
            await browser.clear_permissions()
            
        except Exception as e:
            print(f"Error clearing browser data: {e}")

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

    async def crawl_site(self, domain, user_data_dir, full_extension_path, headless=False, viewport=None):
        """Crawl a website multiple times to analyze cookie persistence"""
        self.base_domain = domain.lower().replace('www.', '')
        visit_results = []
        
        # First get list of URLs to visit (done once)
        print("\nCollecting URLs to visit...")
        urls = []
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
                # Clear ALL data at startup
                await self.clear_all_browser_data(browser)
                
                # Get URLs to visit
                page = browser.pages[0]
                extractor = LinkExtractor(domain)
                urls = await extractor.get_subpages(page, self.max_pages)
                urls = urls[:self.max_pages]  # Ensure max_pages limit
                print(f"Found {len(urls)} URLs to visit")
                
            finally:
                await browser.close()

        # Now do multiple visits with the SAME collected URLs
        for visit in range(self.visits):
            print(f"\nStarting visit {visit + 1} of {self.visits}")
            print(f"Will visit {len(urls)} pages")
            
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
                    await self.network_monitor.setup_monitoring(page, visit_number=visit)
                    await self.fp_collector.setup_monitoring(page)
                    
                    # Visit each URL in this visit
                    for i, url in enumerate(urls, 1):
                        #print(f"\nVisiting page {i}/{len(urls)}: {url}")
                        try:
                            await page.goto(url, timeout=60000)
                            await page.wait_for_load_state('domcontentloaded', timeout=30000)
                            try:
                                await page.wait_for_load_state('networkidle', timeout=10000)
                            except:
                                pass  # Continue if networkidle times out
                            
                            # Capture storage state after each page load
                            await self.network_monitor.storage_monitor.capture_snapshot(page, visit_number=visit)
                            
                            # Simple interaction (scroll)
                            await self.simulate_user_interaction(page)
                        except Exception as e:
                            print(f"Error visiting {url}: {e}")
                    
                    # Store results for this visit
                    visit_results.append({
                        'visit_number': visit,
                        'network': self.network_monitor.get_results(),
                        'fingerprinting': self.fp_collector.get_fingerprinting_results()
                    })
                    
                finally:
                    await browser.close()
        
        # Analyze persistence between visits
        persistent_cookies = self.network_monitor.analyze_cookie_persistence(visit_results)
        
        return {
            'visits': visit_results,
            'persistent_cookies': persistent_cookies,
            'fingerprinting': self.fp_collector.get_fingerprinting_results()
        }