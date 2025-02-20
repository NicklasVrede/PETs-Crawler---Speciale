from playwright.async_api import async_playwright
from .link_extractor import LinkExtractor
from .monitors.network_monitor import NetworkMonitor

class WebsiteCrawler:
    def __init__(self, max_pages=20):
        self.max_pages = max_pages
        self.network_monitor = NetworkMonitor()

    async def crawl_site(self, domain):
        """Crawl a website and extract subpages"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800}
            )
            page = await context.new_page()
            
            # Setup monitoring BEFORE any navigation
            await self.network_monitor.setup_monitoring(page)
            
            print(f"\nCrawling {domain}...")
            
            try:
                # Now navigate and extract links
                extractor = LinkExtractor(domain)
                urls = await extractor.get_subpages(page, self.max_pages)
                return urls
            finally:
                await browser.close() 