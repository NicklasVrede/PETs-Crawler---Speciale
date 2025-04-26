from playwright.async_api import async_playwright
from crawler.monitors.network_monitor import NetworkMonitor
from crawler.monitors.fingerprint_collector import FingerprintCollector
from crawler.monitors.storage_monitor import StorageMonitor
from crawler.monitors.banner_monitor import BannerMonitor
from datetime import datetime
from tqdm import tqdm
import random
import asyncio
from utils.page_collector import load_site_pages
from utils.user_simulator import UserSimulator
import os
import json
from kameleo.local_api_client import KameleoLocalApiClient
from pprint import pprint
import time


class WebsiteCrawler:
    def __init__(self, domain, profile_name, profile_id, subpages_nr=20, visits=2, verbose=False, monitors=None, extension_name=None, headless=False, viewport=None, kameleo_client=None):
        """
        Initialize website crawler with specified parameters
        
        Args:
            domain: Website domain to crawl
            profile_name: Name of the Kameleo profile
            profile_id: ID of the Kameleo profile
            subpages_nr: Number of subpages to visit
            visits: Number of times to visit the domain
            verbose: Whether to print verbose logs
            monitors: Dictionary of monitors to use
            extension_name: Name of the extension to monitor
            headless: Whether to run the browser in headless mode
            viewport: Viewport size for the browser
            kameleo_client: Existing KameleoLocalApiClient instance (optional)
        """
        self.domain = domain
        self.profile_name = profile_name
        self.profile_id = profile_id
        self.subpages_nr = subpages_nr
        self.visits = visits
        self.verbose = verbose
        self.base_domain = domain.lower().replace('www.', '')
        self.extension_name = extension_name
        self.headless = headless
        self.viewport = viewport
        self.user_simulator = UserSimulator()
        self.kameleo_client = kameleo_client

        # Use provided monitors or create defaults
        self.monitors = monitors or {
            'network': NetworkMonitor(verbose=verbose),
            'storage': StorageMonitor(verbose=verbose),
            'fingerprint': FingerprintCollector(verbose=verbose),
            'banner': BannerMonitor(verbose=verbose)
        }

    def _log(self, message):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            tqdm.write(message)

    async def _setup_browser(self, p):
        """Setup browser with context and return existing page"""
        browser_ws_endpoint = f"ws://localhost:5050/playwright/{self.profile_id}"
        try:
            browser = await p.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint,
                                                        timeout=60000)
            context = browser.contexts[0]
            await self._close_extra_tabs(context)
            return context
        except Exception as e:
            tqdm.write(f"Error setting up browser: {e}")    
            raise e

    def _requires_tab_monitoring(self):
        """Check if the current extension requires ongoing tab monitoring"""
        # List of extensions that need continuous tab monitoring
        monitored_extensions = ["adblock", "adblockplus", "ublock", "disconnect"]
        
        # Check if current extension name contains any monitored extension strings
        return any(ext in self.extension_name.lower() for ext in monitored_extensions)

    def _setup_tab_monitoring(self, context):
        """Set up a task to periodically check for and close extra tabs"""
        self._log(f"Setting up continuous tab monitoring for {self.extension_name}")
        
        # Store context for later access by monitoring task
        self._monitored_context = context
        
        # Flag to control the monitoring loop
        self._continue_monitoring = True
        
        # Start the monitoring tasks    
        asyncio.create_task(self._monitor_tabs_task())

    async def _monitor_tabs_task(self):
        """Task that periodically checks for and closes extra tabs"""
        try:
            while self._continue_monitoring:
                # Check for extra tabs every 3 seconds
                await asyncio.sleep(3)
                
                # Skip if context is no longer valid
                if not hasattr(self, '_monitored_context'):
                    break
                    
                try:
                    context = self._monitored_context
                    pages = context.pages
                    
                    # Close any tabs beyond the first one
                    if len(pages) > 1:
                        self._log(f"Tab monitor: Found {len(pages) - 1} extra tab(s). Closing them.")
                        
                        # Close all but the first tab
                        for i in range(1, len(pages)):
                            try:
                                await pages[i].close()
                            except Exception:
                                # Silently continue if we can't close a tab
                                pass
                except Exception:
                    # Ignore errors since this is a background task
                    pass
        except Exception as e:
            tqdm.write(f"Tab monitoring task error: {e}")
        finally:
            self._continue_monitoring = False

    async def _close_extra_tabs(self, context):
        """Close any tabs beyond the first one (which might be opened by extensions)"""
        wait_time = 1.5
        
        # For AdBlock extensions, wait longer for initial tab to appear
        if "adblock" in self.extension_name.lower():
            wait_time = 3.0
            self._log(f"Using longer wait time for {self.extension_name} tabs")
        
        # Wait for extension tabs to fully open
        await asyncio.sleep(wait_time)
        
        # Get all pages in the context
        pages = context.pages
        
        if len(pages) > 1:
            self._log(f"Found {len(pages) - 1} extra tab(s) opened by extensions. Closing them.")
            
            # Close all pages except the first one
            for i in range(1, len(pages)):
                try:
                    await pages[i].close()
                except Exception as e:
                    tqdm.write(f"Error closing tab {i}: {str(e)}")
        
        # Make sure we have at least one page open
        if len(context.pages) == 0:
            self._log("Creating a new page as all were closed")
            await context.new_page()

    async def _clear_browser_data(self, context):
        """Clear browser data"""
        await context.clear_cookies()
        await context.clear_permissions()

        # Use page-level JavaScript to clear storage with error handling
        page = context.pages[0] if context.pages else None
        if page:
            try:
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
                tqdm.write(f"Note: Could not clear page storage: {e}")

    async def _stop_profile(self, context):
        """Stop the Kameleo profile
        context.close() does not work, neither does browser.close()..
        So we close all the pages one by one. The local API method for closing 
        the profile inconsistent. 
        """
        for page in context.pages:
            try:
                await page.close()
            except Exception as e:
                tqdm.write(f"Error closing page: {e}")
        #give time for the profile to close
        return await asyncio.sleep(5)

    async def crawl_site(self, domain, user_data_dir=None, full_extension_path=None, headless=False, viewport=None):
        """Crawl a website multiple times to analyze cookie persistence"""
        self.base_domain = domain.lower().replace('www.', '')

        visit_results = []

        # Load pre-collected URLs
        urls = await self._load_pre_collected_urls(domain)
        if not urls:
            return {'null': 'no urls found'}


        for visit in range(self.visits):
            visited_in_this_cycle = []

            # Browser session for this visit
            async with async_playwright() as p:
                # Set up browser for this visit
                context = await self._setup_browser(p)
                page = context.pages[0] 
                
                # Clear browser data only on first visit
                if visit == 0:
                    self._log("\nClearing browser data...")
                    await self._clear_browser_data(context)
                    self._log("✓ Browser data cleared")
                
                # Setup monitoring
                await self._setup_monitoring(page, visit)

                # Visit the homepage
                await self._visit_homepage(page, domain)

                # Visit URLs
                visited_in_this_cycle = await self._visit_urls(page, urls, visit)

                # Collect visit results
                visit_results.append(await self._collect_visit_results(visit, visited_in_this_cycle))

                # Stop the Kameleo profile after each visit
                await self._stop_profile(context)
        
        # Construct and save the final data structure
        return await self._construct_final_data(domain, visit_results)

    async def _load_pre_collected_urls(self, domain):
        """Load pre-collected URLs from a specified directory"""
        self._log("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages", count=self.subpages_nr)
        if not urls or len(urls) == 0:
            tqdm.write(f"ERROR: No pre-collected URLs found for {domain}")
            return None
        self._log(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        return urls

    async def _setup_monitoring(self, page, visit):
        """Setup network, fingerprint, and storage monitoring"""
        await self.monitors['network'].setup_monitoring(page, visit)
        await self.monitors['fingerprint'].setup_monitoring(page, visit)
        await self.monitors['storage'].setup_monitoring(page)

    async def _visit_homepage(self, page, domain):
        """Visit the homepage and handle any errors"""
        self._log("\nVisiting homepage...")
        homepage_url = f"https://{domain}"
        try:
            await page.goto(homepage_url, timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            self._log(f"Error visiting homepage: {e}")

    async def _visit_urls(self, page, urls, visit):
        """Visit each URL and simulate user interaction"""
        visited_in_this_cycle = []
        
        for idx, url in enumerate(urls):
            try:
                # Shorten URL for display
                display_url = url
                if '?' in url:
                    # Show only domain and path, no query parameters
                    display_url = url.split('?')[0] + '...'
                elif len(url) > 70:
                    # If URL is too long even without parameters, truncate it
                    display_url = url[:70] + '...'
                
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(random.uniform(2000, 3000))
                
                # Check for extension-opened tabs after each page load for monitored extensions
                if self._requires_tab_monitoring():
                    context = page.context
                    if len(context.pages) > 1:
                        self._log(f"Found new tab(s) after loading {display_url}. Closing...")
                        
                        # Close all tabs after the first one
                        for i in range(1, len(context.pages)):
                            try:
                                await context.pages[i].close()
                            except Exception:
                                pass
                
                final_url = page.url
                
                # On the first subpage, capture banner state
                if idx == 0 and 'banner' in self.monitors:
                    try:
                        # Pass current values as fallbacks
                        await self.monitors['banner'].capture_on_subpage(
                            page, 
                            domain=self.base_domain,
                            visit_number=visit,
                            extension_name=self.extension_name
                        )
                    except Exception as e:
                        tqdm.write(f"Error in banner capture: {e}")
                    
                visited_in_this_cycle.append({"original": url, "final": final_url})
                
                # Capture storage after visiting
                if 'storage' in self.monitors:
                    await self.monitors['storage'].capture_snapshot(page, visit_number=visit)
                    
                # Simulate user interaction
                await self.user_simulator.simulate_interaction(page, url=url)
                
            except Exception as e:
                tqdm.write(f"Error visiting {url}: {e}")
                visited_in_this_cycle.append({"original": url, "error": str(e)})
                
        return visited_in_this_cycle

    async def _collect_visit_results(self, visit, visited_in_this_cycle):
        """Collect and structure the results of each visit"""
        return {
            'visit_number': visit,
            'network': self.monitors['network'].get_results()['network_data'],
            'visited_urls': visited_in_this_cycle
        }

    async def _construct_final_data(self, domain, visit_results):
        """Construct the final data structure and save it using CrawlDataManager"""
        
        # Create a new network_data structure with visit numbers as keys
        network_data = {}
        
        for visit in visit_results:
            visit_number = visit['visit_number']
            
            # Store network requests and visited URLs by visit number
            network_data[str(visit_number)] = {
                'requests': visit['network']['requests'],
                'domains_contacted': visit['network']['domains_contacted'],
                'visited_urls': visit['visited_urls']
            }
            
        final_data = {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'network_data': network_data,
            'statistics': self.monitors['network'].get_statistics(),
            'storage': self.monitors['storage'].get_results(),
            'fingerprinting': self.monitors['fingerprint'].get_fingerprinting_data(),
            'cookies': self.monitors['network'].get_cookies()
        }

        return final_data