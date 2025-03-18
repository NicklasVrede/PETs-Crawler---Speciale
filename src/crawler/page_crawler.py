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
    def __init__(self, max_pages=20, visits=2, verbose=False, monitors=None):
        self.max_pages = max_pages
        self.visits = visits
        self.verbose = verbose
        self.base_domain = None
        self.user_simulator = UserSimulator()
        
        # Use provided monitors or create defaults
        self.monitors = monitors or {
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
        urls = await self._load_pre_collected_urls(domain)
        if not urls:
            return {'visits': [], 'fingerprinting': {}}

        # Initial browser setup
        await self._initial_browser_setup(user_data_dir, full_extension_path, headless, viewport)

        for visit in range(self.visits):
            visited_in_this_cycle = []

            # Browser session for this visit
            async with async_playwright() as p:
                context = await self._setup_browser(p, user_data_dir, full_extension_path, headless, viewport)
                page = await context.new_page()

                # Setup monitoring
                await self._setup_monitoring(page, visit)

                # Visit the homepage
                await self._visit_homepage(page, domain)

                # Visit URLs
                visited_in_this_cycle = await self._visit_urls(page, urls, visit)

                # Collect visit results
                visit_results.append(await self._collect_visit_results(visit, visited_in_this_cycle))

                await context.close()

        # Construct and save the final data structure
        return await self._construct_final_data(domain, visit_results)

    async def _load_pre_collected_urls(self, domain):
        """Load pre-collected URLs from a specified directory"""
        if self.verbose:
            print("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages", count=self.max_pages)
        if not urls or len(urls) == 0:
            print(f"ERROR: No pre-collected URLs found for {domain}")
            return None
        if self.verbose:
            print(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        return urls

    async def _initial_browser_setup(self, user_data_dir, full_extension_path, headless, viewport):
        """Perform initial browser setup and clear data"""
        if self.verbose:
            print("\nInitial browser session to clear data and visit homepage...")
        async with async_playwright() as p:
            context = await self._setup_browser(p, user_data_dir, full_extension_path, headless, viewport)
            if self.verbose:
                print("\nClearing browser data...")
            await self._clear_browser_data(context)
            if self.verbose:
                print("✓ Browser data cleared")
            await context.close()

    async def _setup_monitoring(self, page, visit):
        """Setup network, fingerprint, and storage monitoring"""
        await self.monitors['network'].setup_monitoring(page, visit)
        await self.monitors['fingerprint'].setup_monitoring(page, visit)
        await self.monitors['storage'].setup_monitoring(page)

    async def _visit_homepage(self, page, domain):
        """Visit the homepage and handle any errors"""
        if self.verbose:
            print("\nVisiting homepage...")
        homepage_url = f"https://{domain}"
        try:
            await page.goto(homepage_url, timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            if self.verbose:
                print(f"Error visiting homepage: {e}")

    async def _visit_urls(self, page, urls, visit):
        """Visit each URL and simulate user interaction"""
        visited_in_this_cycle = []
        for url in urls:
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(random.uniform(1000, 2000))
                final_url = page.url
                visited_in_this_cycle.append({"original": url, "final": final_url})
                await self.monitors['storage'].capture_snapshot(page, visit_number=visit)
                await self.user_simulator.simulate_interaction(page)
            except Exception as e:
                print(f"Error visiting {url}: {e}")
                visited_in_this_cycle.append({"original": url, "error": str(e)})
        return visited_in_this_cycle

    async def _collect_visit_results(self, visit, visited_in_this_cycle):
        """Collect and structure the results of each visit"""
        return {
            'visit_number': visit,
            'network': self.monitors['network'].get_results()['network_data'],
            'statistics': self.monitors['network'].get_statistics(),
            'storage': self.monitors['storage'].get_results(),
            'fingerprinting': self.monitors['fingerprint']._get_results_for_visit(visit),
            'visited_urls': visited_in_this_cycle
        }

    async def _construct_final_data(self, domain, visit_results):
        """Construct the final data structure and save it using CrawlDataManager"""
        final_data = {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'visits': visit_results,
            'network_data': self.monitors['network'].get_network_data(),
            'statistics': self.monitors['network'].get_statistics(),
            'storage': self.monitors['storage'].get_results(),
            'fingerprinting': self.monitors['fingerprint'].get_fingerprinting_data(),
            'cookies': self.monitors['network'].get_cookies()
        }

        return final_data