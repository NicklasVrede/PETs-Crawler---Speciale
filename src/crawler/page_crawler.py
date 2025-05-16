from playwright.async_api import async_playwright, Error as PlaywrightError
from crawler.monitors.network_monitor import NetworkMonitor
from crawler.monitors.fingerprint_collector import FingerprintCollector
from crawler.monitors.storage_monitor import StorageMonitor
from crawler.monitors.banner_monitor import BannerMonitor
from datetime import datetime
from tqdm import tqdm
import asyncio
import random
from utils.page_collector import load_site_pages
from utils.user_simulator import UserSimulator
from playwright_stealth import Stealth


class WebsiteCrawler:
    def __init__(self, subpages_nr=20, visits=2, verbose=False, monitors=None, extension_name=None, headless=False, viewport=None, domain=None, channel=None):
        """Initialize the crawler with configuration parameters"""
        self.subpages_nr = subpages_nr
        self.visits = visits
        self.verbose = verbose
        self.base_domain = domain.lower().replace('www.', '')
        self.extension_name = extension_name or "no_extension"
        self.headless = headless
        self.viewport = viewport
        self.user_simulator = UserSimulator()
        self.stealth = Stealth()
        self.channel = channel
        self.playwright = None  # Store the Playwright instance

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


    async def _setup_browser(self, p, user_data_dir, full_extension_path, headless, viewport):
        """Setup browser context and clear cookies."""
        browser_args = {}
        
        # Only add extension arguments if an extension is specified
        if full_extension_path and full_extension_path != "no_extension":
            browser_args["args"] = [
                f'--disable-extensions-except={full_extension_path}',
                f'--load-extension={full_extension_path}',
                f'--window-position=9999,9999' # To avoid taking screenspace
            ]
        else:
            browser_args["args"] = [
                f'--window-position=9999,9999'
            ]

        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            viewport=self.viewport,
            channel=self.channel,
            **browser_args
        )

        # Clear cookies context-wide before any navigation in this visit
        try:
            await context.clear_cookies()
            self._log("Cleared cookies for the new visit.")
        except Exception as e:
            self._log(f"Warning: Could not clear cookies: {e}")


        extensions_with_extra_tabs = ["adblock", "disconnect", "decentraleyes"]
        

        if self.extension_name.lower() in extensions_with_extra_tabs:   
            await self._close_extra_tabs(context, profile=self.extension_name)

        await self.stealth.apply_stealth_async(context)

        
        return context


    async def _close_extra_tabs(self, context, profile, max_recursion=10):
        """Closes any browser tabs beyond the first one."""
        await asyncio.sleep(1) # Wait for tab to open.

        pages = context.pages

        # Close pages from the newest back to the second page (index 1)
        if len(pages) > 1:
            self._log(f"Closing {len(pages) - 1} extra tab(s) at startup for profile: {profile}")
            try:
                await pages[1].close()

                #resize the window to the viewport size
                await asyncio.sleep(0.5)
                page = context.pages[0]
                try:
                    await page.set_viewport_size(self.viewport)
                except Exception as e:
                    tqdm.write(f"Error setting viewport size: {e}")
            except Exception as e:
                tqdm.write(f"Error closing extra tab: {e}")
        else:
            #We try again.
            if max_recursion > 0:
                await self._close_extra_tabs(context, profile=self.extension_name, max_recursion=max_recursion-1)
            else:
                tqdm.write(f"Max recursion reached for profile: {profile}")

    async def crawl_site(self, domain, user_data_dir=None, full_extension_path=None, headless=False, viewport=None):
        self.base_domain = domain.lower().replace('www.', '')
        visit_results = []
        urls = await self._load_pre_collected_urls(domain)
        if not urls:
            self._log(f"No pre-collected URLs found for {domain}. Skipping.")
            return {'domain': domain, 'error': 'no_urls_found', 'timestamp': datetime.now().isoformat()}

        # Start Playwright only once per crawl
        try:
            self.playwright = await async_playwright().start()
            self._log("Started Playwright instance for entire crawl")
            
            for visit in range(self.visits):
                # Add global timeout for entire visit (set to 10 minutes)
                visit_timeout = 90_00 
                try:
                    # Use asyncio.wait_for to enforce a global timeout for the entire visit
                    await asyncio.wait_for(
                        self._perform_visit(domain, visit, urls, user_data_dir, full_extension_path, headless, viewport, visit_results),
                        timeout=visit_timeout
                    )
                except asyncio.TimeoutError:
                    tqdm.write(f"TIMEOUT: Visit {visit} ({self.extension_name}) for {domain} timed out after {visit_timeout} seconds")
                    if visit == 0:
                        return {'domain': domain, 'error': f'visit_0_timeout', 'timestamp': datetime.now().isoformat()}
                    # If timeout occurs after the first visit, we continue with next visit
        finally:
            # Close Playwright once at the end of all visits
            if self.playwright:
                try:
                    await self.playwright.stop()
                    self._log("Playwright instance stopped at end of crawl")
                except Exception as p_err:
                    tqdm.write(f"WARNING: Error stopping Playwright for {domain}: {p_err}")
                self.playwright = None

        if visit_results:
            # Construct final data if there were successful visits
            return await self._construct_final_data(domain, visit_results)
        else:
            # Handle cases where no visits completed successfully
            tqdm.write(f"No successful visits completed for {domain}.")
            error_reason = 'no_visits_completed'
            # Check if the loop ran at all (visits > 0) and still no results
            if self.visits > 0 and not visit_results:
                 error_reason = 'first_visit_failed_or_all_failed'
            return {'domain': domain, 'error': error_reason, 'timestamp': datetime.now().isoformat()}

    async def _load_pre_collected_urls(self, domain):
        """Load pre-collected URLs from a specified directory"""
        self._log("\nLoading pre-collected URLs...")
        urls = load_site_pages(domain, input_dir="data/site_pages_final", count=self.subpages_nr)
        if not urls or len(urls) == 0:
            tqdm.write(f"ERROR: No pre-collected URLs found for {domain}")
            return None
        self._log(f"Loaded {len(urls)} pre-collected URLs for {domain}")
        return urls

    async def _setup_monitoring(self, page, visit):
        """Setup network, fingerprint, and storage monitoring"""
        # No need to apply stealth mode here anymore, as it's applied at the context level
        
        # Continue with your existing monitoring setup
        await self.monitors['network'].setup_monitoring(page, visit)
        await self.monitors['fingerprint'].setup_monitoring(page, visit)
        await self.monitors['storage'].setup_monitoring(page)

    async def _capture_and_interact(self, page, url, visit, idx):
        """Captures data (final URL, banner, storage) and simulates interaction."""
        final_url = page.url

        if idx == 1:
            await self.monitors['banner'].capture_on_subpage(
                page, domain=self.base_domain, visit_number=visit, extension_name=self.extension_name
            )

        await self.monitors['storage'].capture_snapshot(page, visit_number=visit)

        simulation_timeout = 15
        try:
            self._log(f"Starting interaction for {url} with timeout {simulation_timeout}s")
            await asyncio.wait_for(
                self.user_simulator.simulate_interaction(page, url=url),
                timeout=simulation_timeout
            )
            self._log(f"User simulation finished for {url}")
        except asyncio.TimeoutError:
            tqdm.write(f"User simulation for {url} ({self.extension_name}) timed out after {simulation_timeout}s.")
        except Exception as sim_err:
            tqdm.write(f"Error during user simulation for {url}: {sim_err}")

        return final_url

    async def _visit_urls(self, page, urls, visit):
        """Visit each URL, capture data, interact, and record results/errors."""
        visited_in_this_cycle = []

        for idx, url in enumerate(urls):
            final_url = None
            error_message = None

            try:
                await page.goto(url, timeout=2000)

                try:
                    await page.wait_for_load_state('domcontentloaded', timeout=2000)
                except Exception as e:
                    self._log(f"Note: domcontentloaded not reached for {url} - continuing anyway")

                try:
                    pass
                    #await page.wait_for_load_state('load', timeout=2000)
                except Exception as e:
                    pass
                    #self._log(f"Note: load not reached for {url} - continuing anyway")

                # Optional: Short wait for network to settle, but with reduced timeout
                try:
                    await page.wait_for_load_state('networkidle', timeout=2000)
                except Exception as e:
                    # This is expected to fail sometimes, so just log at debug level
                    self._log(f"Note: networkidle not reached for {url} - continuing anyway")

                #tqdm.write(f"Capturing and interacting with {url}")
                final_url = await self._capture_and_interact(page, url, visit, idx)

                # Wait abit after scroll
                await asyncio.sleep(random.uniform(0.5, 0.7))

            except Exception as e:
                error_message = str(e)

            result = {"original": url}
            if error_message:
                result["error"] = error_message
            else:

                result["final"] = final_url
            visited_in_this_cycle.append(result)

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

    async def _perform_visit(self, domain, visit, urls, user_data_dir, full_extension_path, headless, viewport, visit_results):
        """Encapsulate a single visit for timeout handling"""
        context = None
        page = None  # Initialize page to None
        
        try:
            # Setup browser context using the class-level Playwright instance
            context = await self._setup_browser(self.playwright, user_data_dir, full_extension_path, headless, viewport)
            page = context.pages[0]  # Assumes setup provides at least one page

            # Setup monitors
            await self._setup_monitoring(page, visit)

            # Visit subpages
            visited_in_this_cycle = await self._visit_urls(page, urls, visit)
            
            # Collect results for this visit before teardown
            visit_data = await self._collect_visit_results(visit, visited_in_this_cycle)
            visit_results.append(visit_data)

            # Clear local/session storage at the end of the visit (after all measurements)
            try:
                await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
                self._log("Cleared local and session storage at the end of the visit.")
            except Exception as e:
                self._log(f"Warning: Could not clear local/session storage: {e}")

        except Exception as visit_err:
            self._log(f"Error during visit {visit} for {domain}: {visit_err}")
            # Log the full traceback for debugging
            import traceback
            traceback.print_exc()
            if visit == 0:
                 self._log(f"Aborting crawl for {domain} due to error on first visit setup/execution.")
                 raise  # Re-raise to be caught by the timeout handler

        finally:
            # Ensure cleanup happens even if errors occur
            self._log(f"Starting cleanup for visit {visit}, domain {domain}...")
            
            if context:
                try:
                    # Use a timeout for context closing
                    await asyncio.wait_for(context.close(), timeout=10.0)
                    self._log("Browser context closed.")
                except Exception as context_err:
                    tqdm.write(f"WARNING: Error closing context for visit {visit}, domain {domain}: {context_err}, profile: {self.extension_name}")
            
            self._log(f"Finished cleanup for visit {visit}, domain {domain}.")