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

    async def crawl_site(self, domain):
        """Crawl a website and collect data"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800}
            )
            page = await context.new_page()
            
            # Setup monitoring
            await self.network_monitor.setup_monitoring(page)
            await self.fp_collector.setup_monitoring(page)
            
            print(f"\nCrawling {domain}...")
            
            try:
                # Crawl the site
                extractor = LinkExtractor(domain)
                urls = await extractor.get_subpages(page, self.max_pages)
                
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
                
                # Save to file
                output_dir = Path('data/baseline')
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_file = output_dir / f"{domain}.json"
                with open(output_file, 'w') as f:
                    json.dump(site_data, f, indent=2)
                
                print(f"\nResults saved to {output_file}")
                if fp_results['fingerprinting_detected']:
                    print(f"Found {len(fp_results['suspicious_scripts'])} suspicious scripts")
                    
                return site_data
                
            finally:
                await browser.close() 