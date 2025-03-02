from urllib.parse import urlparse
from collections import deque
import asyncio

class LinkExtractor:
    def __init__(self, base_domain):
        # Strip 'www.' if present in the base domain
        self.base_domain = base_domain.lower().replace('www.', '')
        self.visited_urls = set()
        self.to_visit = deque()
        self.found_urls = set()

    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            return domain == self.base_domain
        except:
            return False

    def normalize_url(self, url):
        """Normalize URL by removing query parameters and fragments"""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except:
            return url

    async def extract_links(self, page):
        """Extract all links from the current page"""
        links = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(link => link.href)
                .filter(href => href && href.startsWith('http'));
        }''')
        
        # Filter and normalize links
        internal_links = set()
        for url in links:
            if self.is_same_domain(url):
                normalized_url = self.normalize_url(url)
                if normalized_url not in self.visited_urls:
                    internal_links.add(normalized_url)
        
        return internal_links

    async def get_subpages(self, page, max_pages=20):
        """Get subpages from a website up to max_pages"""
        start_url = f"https://{self.base_domain}"
        
        try:
            # Visit homepage
            await page.goto(start_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            await page.wait_for_load_state('networkidle', timeout=5000)
            
            # Get initial links
            internal_links = await self.extract_links(page)
            
            # Add to collections
            self.found_urls.add(start_url)
            self.found_urls.update(internal_links)
            self.visited_urls.add(start_url)
            
            # Add unvisited links to queue
            self.to_visit.extend(link for link in internal_links 
                               if link not in self.visited_urls)
            
            # Visit subpages 
            while len(self.found_urls) < max_pages and self.to_visit:
                next_url = self.to_visit.popleft()
                if next_url in self.visited_urls:
                    continue
                
                try:
                    await page.goto(next_url, timeout=30000)
                    await page.wait_for_load_state('domcontentloaded')
                    subpage_links = await self.extract_links(page)
                    
                    # Only add new links
                    new_links = subpage_links - self.visited_urls
                    self.found_urls.update(new_links)
                    self.visited_urls.add(next_url)
                    self.to_visit.extend(new_links)
                    
                except Exception as e:
                    continue
            
            return list(self.found_urls)[:max_pages]
            
        except Exception as e:
            return []