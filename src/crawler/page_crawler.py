from playwright.async_api import async_playwright, TimeoutError
from crawler.monitors.network_monitor import NetworkMonitor
from crawler.monitors.fingerprint_collector import FingerprintCollector
from crawler.monitors.storage_monitor import StorageMonitor
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
    def __init__(self, max_pages=20, visits=2, verbose=False, show_progress=False):
        self.max_pages = max_pages
        self.visits = visits
        self.verbose = verbose
        self.base_domain = None
        self.user_simulator = UserSimulator(verbose=verbose)
        self.show_progress = show_progress
        
        # Initialize monitors
        self.monitors = {
            'network': NetworkMonitor(verbose=verbose),
            'storage': StorageMonitor(verbose=verbose),
            'fingerprint': FingerprintCollector(verbose=verbose)
        }

    async def clear_all_browser_data(self, context):
        """Clear browser data between visits"""
        if self.verbose:
            print("\nClearing browser data...")
        try:
            # Clear context-level data
            if self.verbose:
                print("Clearing context-level data...")
            await context.clear_cookies()
            await asyncio.sleep(1)
            await context.clear_permissions()
            await asyncio.sleep(1)
            
            # Use page-level JavaScript to clear storage with error handling
            page = context.pages[0] if context.pages else None
            if page:
                if self.verbose:
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
                    if self.verbose:
                        print(f"Note: Could not clear page storage: {e}")
            
            if self.verbose:
                print("✓ Browser data cleared")
            
        except Exception as e:
            if self.verbose:
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

    async def launch_browser(self, user_data_dir=None, full_extension_path=None, headless=False):
        """Launch a browser with the specified settings"""
        playwright = await async_playwright().start()
        
        # Prepare browser arguments for extensions if needed
        browser_args = []
        if full_extension_path:
            browser_args.append(f"--disable-extensions-except={full_extension_path}")
            browser_args.append(f"--load-extension={full_extension_path}")
        
        # Different launch method based on whether we need a user data directory
        if user_data_dir:
            # Use launch_persistent_context when a user data directory is specified
            browser_context = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                args=browser_args
            )
            # Store reference to the playwright instance
            browser_context._playwright = playwright
            # For consistent API, return an object with a similar structure to what we'd get from launch()
            # This creates a browser-like object with a new_context method that just returns the persistent context
            class BrowserWrapper:
                def __init__(self, context, playwright):
                    self.context = context
                    self._playwright = playwright
                    
                async def close(self):
                    await self.context.close()
                    
                async def new_context(self, **kwargs):
                    # Just return the existing context since we're using a persistent context
                    return self.context
            
            return BrowserWrapper(browser_context, playwright)
        else:
            # Standard launch for cases without a user data directory
            browser = await playwright.chromium.launch(
                headless=headless,
                args=browser_args
            )
            browser._playwright = playwright
            return browser

    async def crawl_site(self, domain, user_data_dir=None, full_extension_path=None, headless=False, viewport=None):
        """Crawl a website multiple times to analyze cookie persistence"""
        self.base_domain = domain.lower().replace('www.', '')
        visit_results = []
        browser = None
        
        # Load pre-collected URLs
        if self.verbose:
            print("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages", count=self.max_pages)
        
        if not urls or len(urls) == 0:
            tqdm.write(f"ERROR: No pre-collected URLs found for {domain}")
            return {'visits': [], 'fingerprinting': {}}
        
        if self.verbose:
            tqdm.write(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        
        try:
            # Calculate total pages to visit across all visits
            total_pages = len(urls) * self.visits
            
            # Create progress bar if show_progress is True
            pbar = None
            if self.show_progress:
                pbar = tqdm(total=total_pages, desc=f"Visiting {domain}", unit="page")
            
            # Multiple visits to analyze cookie persistence
            for visit in range(1, self.visits + 1):
                # Launch the browser for each visit
                try:
                    # Use our helper function to launch the browser
                    browser = await self.launch_browser(
                        user_data_dir=user_data_dir,
                        full_extension_path=full_extension_path,
                        headless=headless
                    )
                    
                    # Create a new context with the desired viewport
                    context = await browser.new_context(
                        viewport=viewport or {"width": 1280, "height": 800}
                    )
                    
                    # Initialize list to keep track of visited URLs in this cycle
                    visited_in_this_cycle = []
                    
                    # Reset monitors for this visit
                    for monitor in self.monitors.values():
                        if hasattr(monitor, 'reset'):
                            monitor.reset()
                    
                    # Update progress bar description to show current visit
                    if pbar:
                        pbar.set_description(f"Visiting {domain} (visit {visit}/{self.visits})")
                    
                    # Visit each URL in the list
                    for url in urls:
                        try:
                            # Create a new page
                            page = await context.new_page()
                            
                            try:
                                # Set up page monitors - properly handle different monitor interfaces
                                for name, monitor in self.monitors.items():
                                    if name == 'storage':
                                        # For storage monitor, pass the visit number to capture_snapshot
                                        # but not to setup_monitoring
                                        if hasattr(monitor, 'setup_monitoring'):
                                            await monitor.setup_monitoring(page)
                                    elif name == 'fingerprint':
                                        # For fingerprint monitor, it needs the visit for setup
                                        if hasattr(monitor, 'setup_monitoring'):
                                            await monitor.setup_monitoring(page, visit)
                                    elif hasattr(monitor, 'setup_page'):
                                        await monitor.setup_page(page, self.base_domain)
                                
                                # Go to the URL with a timeout
                                try:
                                    response = await page.goto(
                                        url,
                                        timeout=30000,
                                        wait_until="domcontentloaded"
                                    )
                                except Exception as e:
                                    tqdm.write(f"\nError navigating to {url}: {e}")
                                    visited_in_this_cycle.append({"original": url, "error": str(e)})
                                    if pbar:
                                        pbar.update(1)
                                    await page.close()
                                    continue
                                
                                # Record the final URL (after redirects)
                                final_url = page.url
                                visited_in_this_cycle.append({"original": url, "final": final_url})
                                
                                # Storage monitor needs the visit number during capture
                                await self.monitors['storage'].capture_snapshot(page, visit_number=visit)
                                await self.user_simulator.simulate_interaction(page, self.base_domain)
                                
                                # Update progress bar if it exists
                                if pbar:
                                    pbar.update(1)
                                    
                            finally:
                                # Make sure page is closed
                                try:
                                    await page.close()
                                except Exception:
                                    # Page might already be closed, ignore errors
                                    pass
                            
                        except Exception as e:
                            tqdm.write(f"\nError handling page for {url}: {e}")
                            visited_in_this_cycle.append({"original": url, "error": str(e)})
                            # Update progress bar if it exists
                            if pbar:
                                pbar.update(1)
                    
                    visit_results.append({
                        'visit_number': visit,
                        'network': self.monitors['network'].get_results()['network_data'],
                        'statistics': self.monitors['network'].get_statistics(),
                        'storage': self.monitors['storage'].get_results(),
                        'fingerprinting': self.monitors['fingerprint']._get_results_for_visit(visit),
                        'visited_urls': visited_in_this_cycle
                    })
                    
                    # Close the context at the end of this visit
                    await context.close()
                    
                except Exception as e:
                    tqdm.write(f"\nError during visit {visit}: {e}")
                finally:
                    # Make sure browser is closed
                    if browser:
                        try:
                            # Close the playwright instance too
                            playwright = getattr(browser, '_playwright', None)
                            await browser.close()
                            if playwright:
                                await playwright.stop()
                        except Exception as e:
                            # Browser might already be closed, ignore errors
                            if self.verbose:
                                print(f"Error closing browser: {e}")
                    browser = None
        
        finally:
            # Close progress bar if it exists
            if pbar:
                pbar.close()
            
            # Make sure browser is closed (redundant but safe)
            if browser:
                try:
                    playwright = getattr(browser, '_playwright', None)
                    await browser.close()
                    if playwright:
                        await playwright.stop()
                except Exception:
                    # Ignore errors during final cleanup
                    pass
        
        return {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'visits': visit_results,
            'network_data': self.monitors['network'].get_network_data(),
            'statistics': self.monitors['network'].get_statistics(),
            'storage': self.monitors['storage'].get_results(),
            'fingerprinting': self.monitors['fingerprint'].get_fingerprinting_data(),
            'cookies': self.monitors['network'].get_cookies()
        }