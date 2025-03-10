import asyncio
import json
import os
from urllib.parse import urlparse
from collections import deque
from playwright.async_api import async_playwright
import sys
import os
from utils.util import construct_paths, load_config, get_profile_config

class PageCollector:
    def __init__(self, base_domain):
        # Strip 'www.' if present in the base domain
        self.base_domain = base_domain.lower().replace('www.', '')
        self.visited_urls = set()
        self.to_visit = deque()
        self.found_urls = []  # Use list to maintain order

    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            # Strip 'www.' from the netloc for comparison
            domain = parsed.netloc.lower().replace('www.', '')
            return domain == self.base_domain
        except Exception as e:
            print(f"Error parsing URL {url}: {e}")
            return False

    async def extract_links(self, page):
        """Extract all links from the current page"""
        links = await page.evaluate('''() => {
            const links = document.querySelectorAll('a[href]');
            const results = [];
            links.forEach(link => {
                try {
                    results.push(link.href);
                } catch (e) {}
            });
            return results;
        }''')
        
        # Filter and clean links
        internal_links = set()
        for url in links:
            if self.is_same_domain(url):
                internal_links.add(url)
        
        return internal_links

    async def collect_pages(self, page, max_pages=40, homepage_links=3):
        """
        Collect subpages from a website
        
        Args:
            page: Playwright page object
            max_pages: Maximum pages to collect
            homepage_links: Number of direct links from homepage to prioritize
        """
        print(f"\n===== Collecting up to {max_pages} pages from {self.base_domain} =====")
        try:
            start_url = f"https://{self.base_domain}/"
            
            # Initial visit to homepage
            print(f"Initial visit to homepage: {start_url}")
            await page.goto(start_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Additional wait for cookie extension to process banners
            await page.wait_for_timeout(1000)
            
            # Wait for network to become idle with a reasonable timeout
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except Exception as e:
                print(f"Network idle timeout on homepage, continuing anyway: {e}")
            
            # Add homepage as first URL
            if start_url not in self.found_urls:
                self.found_urls.append(start_url)
                self.visited_urls.add(start_url)
                print(f"Added homepage: {start_url}")
            
            # Get direct links from homepage
            homepage_direct_links = await self.extract_links(page)
            print(f"Found {len(homepage_direct_links)} links on homepage")
            
            # Add homepage_links direct links first
            direct_link_count = 0
            for link in homepage_direct_links:
                if link not in self.found_urls and link != start_url:
                    self.found_urls.append(link)
                    self.to_visit.append(link)
                    direct_link_count += 1
                    print(f"Added direct homepage link: {link}")
                    
                    if direct_link_count >= homepage_links:
                        break
            
            # Add remaining homepage links to the queue for later
            for link in homepage_direct_links:
                if link not in self.found_urls and link != start_url:
                    self.to_visit.append(link)
            
            # Continue with subpage visits to reach max_pages
            crawl_counter = 1
            
            # Now visit each prioritized link and collect their links
            while len(self.found_urls) < max_pages and self.to_visit:
                next_url = self.to_visit.popleft()
                if next_url in self.visited_urls:
                    continue
                
                print(f"\nCollection step {crawl_counter}: Visiting {next_url}")
                crawl_counter += 1
                
                try:
                    # Fast loading for subpages - just wait for DOM content
                    await page.goto(next_url, wait_until='domcontentloaded', timeout=20000)
                    
                    # Small timeout for cookie extension
                    await page.wait_for_timeout(1000)
                    
                    # Mark as visited
                    self.visited_urls.add(next_url)
                    
                    # Add to found_urls if not already added
                    if next_url not in self.found_urls:
                        self.found_urls.append(next_url)
                        print(f"Added to collection: {next_url}")
                    
                    # Extract links from this subpage
                    subpage_links = await self.extract_links(page)
                    
                    # Add new links to the queue
                    for link in subpage_links:
                        if link not in self.visited_urls and link not in self.found_urls:
                            self.to_visit.append(link)
                    
                    print(f"  Found {len(subpage_links)} internal links")
                    print(f"  Queue now has {len(self.to_visit)} URLs")
                    print(f"  Total pages collected so far: {len(self.found_urls)}")
                    
                except Exception as e:
                    print(f"Error visiting {next_url}: {str(e)}")
            
            # Return up to max_pages URLs
            result_urls = self.found_urls[:max_pages]
            print(f"\n===== Collected {len(result_urls)}/{max_pages} unique pages to analyze =====")
            return result_urls
            
        except Exception as e:
            print(f"Error processing homepage: {str(e)}")
            return []


async def collect_site_pages(domain, max_pages=40, homepage_links=3, setup='i_dont_care_about_cookies'):
    """Run the page collection for a single site"""
    # Load configuration to use the same extension as the main crawler
    config = load_config('config.json')
    profile_config = get_profile_config(config, setup)
    user_data_dir, full_extension_path = construct_paths(config, setup)
    
    print(f"Using extension path: {full_extension_path}")
    print(f"Using user data directory: {user_data_dir}")
    
    # Verify extension path exists
    if not os.path.exists(full_extension_path):
        print(f"ERROR: Extension path does not exist: {full_extension_path}")
        return []
    
    async with async_playwright() as p:
        try:
            # Use launch_persistent_context with the user data directory
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=[
                    f"--disable-extensions-except={full_extension_path}",
                    f"--load-extension={full_extension_path}"
                ],
                viewport=profile_config.get('viewport', {'width': 1280, 'height': 800})
            )
            
            page = await context.new_page()
            
            collector = PageCollector(domain)
            pages = await collector.collect_pages(page, max_pages, homepage_links)
            
            await context.close()
            return pages
            
        except Exception as e:
            print(f"Failed to launch browser with extension: {e}")
            # Try without extension as fallback
            print("Attempting to launch without extension as fallback...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            collector = PageCollector(domain)
            pages = await collector.collect_pages(page, max_pages, homepage_links)
            
            await browser.close()
            return pages


def save_site_pages(domain, pages, output_dir="data/site_pages"):
    """Save collected pages to a JSON file"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a safe filename
    safe_domain = domain.replace(".", "_")
    filename = os.path.join(output_dir, f"{safe_domain}.json")
    
    data = {
        "domain": domain,
        "pages": pages,
        "count": len(pages)
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Saved {len(pages)} pages for {domain} to {filename}")
    return filename


def load_site_pages(domain, input_dir="data/site_pages", count=20):
    """Load collected pages from a JSON file and return the top N"""
    safe_domain = domain.replace(".", "_")
    filename = os.path.join(input_dir, f"{safe_domain}.json")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Get the URLs, limited to count
        pages = data['pages'][:count]
        
        print(f"Loaded top {len(pages)} pages for {domain} from {filename}")
        return pages
    except FileNotFoundError:
        print(f"No saved pages found for {domain}")
        return None


async def main():
    """Collect pages for multiple domains"""
    # List of domains to collect
    domains = [
        "amazon.co.uk",
        "bbc.co.uk",
        "google.com"
        # Add more domains as needed
    ]
    
    # Use the same profile as in the main crawler
    setup = 'i_dont_care_about_cookies'
    
    for domain in domains:
        print(f"\nCollecting pages for {domain}...")
        # Collect 40 pages, with 3 priority links from homepage
        pages = await collect_site_pages(domain, max_pages=40, homepage_links=3, setup=setup)
        if pages:
            save_site_pages(domain, pages)
            
    # Example: print the top 20 for each domain
    for domain in domains:
        top_pages = load_site_pages(domain, count=20)
        if top_pages:
            print(f"\nTop 20 pages for {domain}:")
            for i, url in enumerate(top_pages, 1):
                print(f"{i}. {url}")


if __name__ == "__main__":
    asyncio.run(main()) 