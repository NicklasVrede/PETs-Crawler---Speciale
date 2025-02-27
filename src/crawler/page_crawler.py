from playwright.async_api import async_playwright
from .link_extractor import LinkExtractor
from .monitors.network_monitor import NetworkMonitor
from .monitors.fingerprint_collector import FingerprintCollector
from pathlib import Path
import json
from datetime import datetime

class WebsiteCrawler:
    def __init__(self, max_pages=20):
        self.max_pages = max_pages
        self.network_monitor = NetworkMonitor()
        self.fp_collector = FingerprintCollector()

    async def crawl_site(self, domain, user_data_dir, full_extension_path, headless=False, viewport=None):
        """Crawl a website and collect data using a specified browser executable."""
        async with async_playwright() as p:
            # Launch a persistent context with the specified user data directory and extension
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport=viewport or {'width': 1280, 'height': 800},
                args=[
                    f'--disable-extensions-except={full_extension_path}',
                    f'--load-extension={full_extension_path}'
                ]
            )
            # Reference to the first page:
            page = browser.pages[0]
            
            # Setup monitoring
            await self.network_monitor.setup_monitoring(page)
            await self.fp_collector.setup_monitoring(page)
            
            print(f"\nCrawling {domain}...")
            
            try:
                # Crawl the site
                extractor = LinkExtractor(domain)
                urls = await extractor.get_subpages(page, self.max_pages)
                
                # Visit each URL and collect data
                for url in urls:
                    #print(f"\nVisiting and analyzing: {url}")
                    try:
                        await page.goto(url, timeout=30000)
                        await page.wait_for_load_state('domcontentloaded')
                        # Allow some time for scripts to load and execute
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as e:
                        print(f"Error visiting {url}: {str(e)}")
                        continue
                
                # Get results
                fp_results = self.fp_collector.get_fingerprinting_results()
                
                # Prepare data for storage
                site_data = {
                    'domain': domain,
                    'crawl_time': datetime.now().isoformat(),
                    'pages_crawled': len(urls),
                    'fingerprinting': {
                        'detected': fp_results['fingerprinting_detected'],
                        'suspicious_scripts': fp_results['suspicious_scripts'],
                        'api_calls_by_category': {
                            category: len(calls) 
                            for category, calls in fp_results['api_calls'].items()
                            if calls  # Only include categories with calls
                        }
                    },
                    'scripts': self.network_monitor.script_metadata
                }
                
                return site_data
                
            finally:
                await browser.close()