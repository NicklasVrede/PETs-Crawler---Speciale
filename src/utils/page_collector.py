import asyncio
import json
import os
import csv
from urllib.parse import urlparse
from collections import deque
from playwright.async_api import async_playwright
import sys
import os
from tqdm import tqdm
from utils.util import construct_paths, load_config, get_profile_config

class PageCollector:
    def __init__(self, base_domain):
        # Strip 'www.' if present in the base domain
        self.base_domain = base_domain.lower().replace('www.', '')
        self.visited_urls = set()
        self.to_visit = deque()
        self.found_urls = []  # Use list to maintain order
        self.progress_bar = None

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
        """Extract all visible links from the current page"""
        links = await page.evaluate('''() => {
            // Helper function to check if an element is visible
            function isVisible(elem) {
                if (!elem) return false;
                
                // Check computed style
                const style = window.getComputedStyle(elem);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return false;
                }
                
                // Check dimensions (a 1x1 element is likely invisible)
                const rect = elem.getBoundingClientRect();
                if (rect.width <= 1 || rect.height <= 1) {
                    return false;
                }
                
                // Check if element is within viewport or reasonably close
                const viewportHeight = window.innerHeight;
                const viewportWidth = window.innerWidth;
                // Allow elements slightly outside viewport (200px buffer)
                const buffer = 200;
                if (rect.bottom < -buffer || 
                    rect.top > viewportHeight + buffer || 
                    rect.right < -buffer || 
                    rect.left > viewportWidth + buffer) {
                    return false;
                }
                
                return true;
            }
            
            const links = document.querySelectorAll('a[href]');
            const results = [];
            
            links.forEach(link => {
                try {
                    if (isVisible(link)) {
                        results.push(link.href);
                    }
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
        Collect subpages from a website using multiple chains if needed
        
        Args:
            page: Playwright page object
            max_pages: Maximum pages to collect in total
            homepage_links: Maximum number of chains to try from homepage
        """
        # Initialize progress bar
        self.progress_bar = tqdm(total=max_pages, desc="Collecting URLs", unit="page")
        
        try:
            start_url = f"https://{self.base_domain}/"
            
            # Initial visit to homepage
            await page.goto(start_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            
            # Additional wait for cookie extension to process banners
            await page.wait_for_timeout(1000)
            
            # Wait for network to become idle with a reasonable timeout
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass
            
            # Add homepage as first URL
            self.found_urls.append(start_url)
            self.visited_urls.add(start_url)
            self.progress_bar.update(1)
            
            # Get links from homepage
            homepage_links_list = list(await self.extract_links(page))
            
            # Try to build multiple chains if needed
            chain_start_index = 0
            homepage_links_tried = 0
            
            while len(self.found_urls) < max_pages and homepage_links_tried < homepage_links and chain_start_index < len(homepage_links_list):
                # Get next homepage link to start a chain
                chain_start = None
                while chain_start_index < len(homepage_links_list):
                    potential_start = homepage_links_list[chain_start_index]
                    chain_start_index += 1
                    if potential_start != start_url and potential_start not in self.found_urls:
                        chain_start = potential_start
                        self.found_urls.append(chain_start)
                        self.progress_bar.update(1)
                        break
                
                if not chain_start:
                    break
                    
                homepage_links_tried += 1
                
                # Start chain exploration
                current_url = chain_start
                chain_depth = 1
                chain_visited = {start_url, chain_start}  # Track visited URLs in this chain
                
                # Follow this chain until we find max 10 URLs per chain or can't find more links
                while chain_depth < 10 and len(self.found_urls) < max_pages:
                    try:
                        # Visit the current URL in the chain
                        await page.goto(current_url, wait_until='domcontentloaded', timeout=20000)
                        await page.wait_for_timeout(1000)
                        
                        # Mark as visited
                        self.visited_urls.add(current_url)
                        
                        # Get links from this page
                        page_links = list(await self.extract_links(page))
                        if not page_links:
                            break
                            
                        # Find next link in chain - prioritize unvisited links
                        next_link = None
                        
                        # First try: look for links not in this chain
                        for link in page_links:
                            if link not in chain_visited and link not in self.found_urls:
                                next_link = link
                                self.found_urls.append(link)
                                self.progress_bar.update(1)
                                chain_visited.add(link)
                                break
                        
                        # Second try: accept any unvisited link
                        if not next_link:
                            for link in page_links:
                                if link not in self.visited_urls and link not in self.found_urls:
                                    next_link = link
                                    self.found_urls.append(link)
                                    self.progress_bar.update(1)
                                    chain_visited.add(link)
                                    break
                        
                        # Last resort: just take any link on the page we haven't added to found_urls
                        if not next_link:
                            for link in page_links:
                                if link not in self.found_urls:
                                    next_link = link
                                    self.found_urls.append(link)
                                    self.progress_bar.update(1)
                                    chain_visited.add(link)
                                    break
                        
                        if next_link:
                            current_url = next_link
                            chain_depth += 1
                        else:
                            break
                            
                    except Exception:
                        break
            
            # If we still don't have enough links, just add more from homepage
            if len(self.found_urls) < max_pages and homepage_links_list:
                for link in homepage_links_list:
                    if link not in self.found_urls:
                        self.found_urls.append(link)
                        self.progress_bar.update(1)
                        if len(self.found_urls) >= max_pages:
                            break
            
            # Close the progress bar
            self.progress_bar.close()
            
            # Return collected URLs (up to max_pages)
            result_urls = self.found_urls[:max_pages]
            return result_urls
            
        except Exception as e:
            if self.progress_bar:
                self.progress_bar.close()
            return []


async def collect_site_pages(domain, max_pages=40, homepage_links=3, setup='i_dont_care_about_cookies'):
    """Run the page collection for a single site"""
    # Load configuration to use the same extension as the main crawler
    config = load_config('config.json')
    profile_config = get_profile_config(config, setup)
    user_data_dir, full_extension_path = construct_paths(config, setup)
    
    #print(f"Using extension path: {full_extension_path}")
    #print(f"Using user data directory: {user_data_dir}")
    
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


async def collect_all_site_pages(setup='i_dont_care_about_cookies', max_pages=40, homepage_links=3):
    """Collect pages for all domains in study-sites.csv"""
    # Load domains from CSV
    domains = []
    try:
        with open('data/study-sites.csv', 'r') as f:
            reader = csv.DictReader(f)
            domains = [row['domain'].lower().replace('.', '_') for row in reader]
    except Exception as e:
        print(f"Error loading study-sites.csv: {e}")
        return

    print(f"\nCollecting pages for {len(domains)} domains...")
    
    for domain in domains:
        # Check if file already exists
        file_path = f"data/site_pages/{domain}.json"
        if os.path.exists(file_path):
            print(f"\nSkipping {domain} - already collected")
            continue
            
        print(f"\n{'='*50}")
        print(f"Collecting pages for {domain}...")
        print(f"{'='*50}")
        
        # Convert back to proper domain format for collection
        original_domain = domain.replace('_', '.')
        pages = await collect_site_pages(original_domain, max_pages=max_pages, homepage_links=homepage_links, setup=setup)
        if pages:
            save_site_pages(domain, pages)
            print(f"✓ Saved {len(pages)} pages for {domain}")
        else:
            print(f"✗ No pages collected for {domain}")


if __name__ == "__main__":
    asyncio.run(collect_all_site_pages()) 