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
from playwright_stealth import Stealth


class WebsiteCrawler:
    def __init__(self, max_pages=20, visits=2, verbose=False, monitors=None, extension_name=None):
        """Initialize the crawler with configuration parameters"""
        self.max_pages = max_pages
        self.visits = visits
        self.verbose = verbose
        self.base_domain = None
        self.extension_name = extension_name or "no_extension"
        self.user_simulator = UserSimulator()
        self.stealth = Stealth()
        
        # Use provided monitors or create defaults
        self.monitors = monitors or {
            'network': NetworkMonitor(verbose=verbose),
            'storage': StorageMonitor(verbose=verbose),
            'fingerprint': FingerprintCollector(verbose=verbose),
            'banner': BannerMonitor(verbose=verbose)
        }

    async def _populate_cache(self, page, urls):
        """Pre-populate browser cache with resources from the target site"""
        tqdm.write("\nPre-populating cache with site resources...")
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
                    tqdm.write(f"Error pre-caching {url}: {e}")
                
            tqdm.write("✓ Cache populated with site resources")
        except Exception as e:
            tqdm.write(f"Error during cache population: {e}")

    async def _setup_browser(self, p, user_data_dir, full_extension_path, headless, viewport):
        """Setup browser with context"""
        browser_args = {}
        
        # Only add extension arguments if an extension is specified
        if full_extension_path and full_extension_path != "no_extension":
            browser_args["args"] = [
                f'--disable-extensions-except={full_extension_path}',
                f'--load-extension={full_extension_path}'
            ]

        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport=viewport or {'width': 1280, 'height': 800},
            **browser_args
        )
        
        # Apply stealth to the context (this will affect all pages created from this context)
        await self.stealth.apply_stealth_async(context)
        
        return context

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
                tqdm.write(f"Note: Could not clear page storage: {e}")

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
                
                # Use the existing page instead of creating a new one
                page = context.pages[0]  # Get the first page that's automatically created

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
            tqdm.write("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages", count=self.max_pages)
        if not urls or len(urls) == 0:
            tqdm.write(f"ERROR: No pre-collected URLs found for {domain}")
            return None
        if self.verbose:
            tqdm.write(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        return urls

    async def _initial_browser_setup(self, user_data_dir, full_extension_path, headless, viewport):
        """Perform initial browser setup and clear data"""
        if self.verbose:
            tqdm.write("\nInitial browser session to clear data and visit homepage...")
        async with async_playwright() as p:
            context = await self._setup_browser(p, user_data_dir, full_extension_path, headless, viewport)
            if self.verbose:
                tqdm.write("\nClearing browser data...")
            await self._clear_browser_data(context)
            if self.verbose:
                tqdm.write("✓ Browser data cleared")
            await context.close()

    async def _setup_monitoring(self, page, visit):
        """Setup network, fingerprint, and storage monitoring"""
        # No need to apply stealth mode here anymore, as it's applied at the context level
        
        # Continue with your existing monitoring setup
        await self.monitors['network'].setup_monitoring(page, visit)
        await self.monitors['fingerprint'].setup_monitoring(page, visit)
        await self.monitors['storage'].setup_monitoring(page)

    async def _visit_homepage(self, page, domain):
        """Visit the homepage and handle any errors"""
        if self.verbose:
            tqdm.write("\nVisiting homepage...")
        homepage_url = f"https://{domain}"
        try:
            await page.goto(homepage_url, timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            if self.verbose:
                tqdm.write(f"Error visiting homepage: {e}")

    async def _visit_urls(self, page, urls, visit):
        """Visit each URL and simulate user interaction"""
        visited_in_this_cycle = []
        
        # print(f"\n[DEBUG] Visit #{visit} - About to visit {len(urls)} URLs")
        
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
                
                # print(f"[DEBUG] Visit #{visit} - Navigating to URL #{idx}: {display_url}")
                
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(random.uniform(1000, 2000))
                final_url = page.url
                
                # On the first subpage, capture banner state
                if idx == 0 and 'banner' in self.monitors:
                    # print(f"[DEBUG] Visit #{visit} - Triggering banner monitor capture for {self.base_domain}")
                    try:
                        # Pass current values as fallbacks
                        await self.monitors['banner'].capture_on_subpage(
                            page, 
                            domain=self.base_domain,
                            visit_number=visit,
                            extension_name=self.extension_name
                        )
                    except Exception as e:
                        print(f"Error in banner capture: {e}")
                    
                visited_in_this_cycle.append({"original": url, "final": final_url})
                
                # Capture storage after visiting
                if 'storage' in self.monitors:
                    await self.monitors['storage'].capture_snapshot(page, visit_number=visit)
                    
                # Simulate user interaction
                await self.user_simulator.simulate_interaction(page)
                
            except Exception as e:
                print(f"Error visiting {url}: {e}")
                visited_in_this_cycle.append({"original": url, "error": str(e)})
                
        # print(f"[DEBUG] Visit #{visit} - Completed visiting URLs")
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