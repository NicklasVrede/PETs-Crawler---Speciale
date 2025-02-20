import asyncio
from crawler.page_crawler import WebsiteCrawler
from managers.site_manager import SiteManager

# Configuration
STORAGE_FOLDER = 'baseline'

async def main():
    site_manager = SiteManager(STORAGE_FOLDER)
    rank, domain = site_manager.get_next_site()
    
    # Crawl site
    crawler = WebsiteCrawler(max_pages=20)
    urls = await crawler.crawl_site(domain)
    
    # Debug print
    print(f"\nDebug: Total requests captured: {len(crawler.network_monitor.requests)}")
    
    # Store data
    site_manager.save_site_data(domain, rank, crawler.network_monitor)

if __name__ == "__main__":
    asyncio.run(main())