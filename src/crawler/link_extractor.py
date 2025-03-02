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
            # Strip 'www.' from the netloc for comparison
            domain = parsed.netloc.lower().replace('www.', '')
            return domain == self.base_domain
        except Exception as e:
            print(f"Error parsing URL {url}: {e}")
            return False

    async def extract_links(self, page):
        """Extract all links from the current page"""
        # First, let's see what we're working with
        #print("\nDEBUG: Checking page content...")
        
        # Get all links with href attributes
        links = await page.evaluate('''() => {
            console.log("Starting link extraction...");
            const links = document.querySelectorAll('a[href]');
            console.log("Found " + links.length + " links");
            
            const results = [];
            links.forEach(link => {
                try {
                    const href = link.href;
                    console.log("Found link: " + href);
                    results.push(href);
                } catch (e) {
                    console.log("Error with link: " + e);
                }
            });
            return results;
        }''')
        
        #print(f"DEBUG: Raw links found: {len(links)}")
        #print("DEBUG: First 5 raw links:", links[:5])
        
        # Debug domain comparison
        test_url = links[0] if links else None
        if test_url:
            parsed = urlparse(test_url)
            test_domain = parsed.netloc.lower().replace('www.', '')
            #print(f"DEBUG: Comparing domains:")
            #print(f"  Base domain: {self.base_domain}")
            #print(f"  Test domain: {test_domain}")
        
        # Filter and clean links
        internal_links = set()
        for url in links:
            try:
                if self.is_same_domain(url):
                    #print(f"DEBUG: Found internal link: {url}")
                    internal_links.add(url)
                else:
                    #print(f"DEBUG: External link: {url}")
                    pass
            except Exception as e:
                #print(f"DEBUG: Error processing URL {url}: {e}")
                pass
        
        #print(f"DEBUG: Found {len(internal_links)} internal links")
        return internal_links

    async def get_subpages(self, page, max_pages=20):
        """Get subpages from a website up to max_pages"""
        start_url = f"https://{self.base_domain}"
        
        # Visit homepage with better loading strategy
        print(f"Visiting homepage: {start_url}")
        try:
            await page.goto(start_url, timeout=30000)
            print("   Waiting for DOM content...")
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            print("   Waiting for network...")
            await page.wait_for_load_state('networkidle', timeout=5000)
            print("   Waiting extra time for dynamic content...")
            await asyncio.sleep(2)  # Wait for dynamic content
            
            # Wait for any <a> tags to appear
            print("   Waiting for links to appear...")
            await page.wait_for_selector('a[href]', timeout=5000)
            
            # Get links with more detailed JavaScript
            links = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => {
                    try {
                        return new URL(link.href).href;
                    } catch {
                        return null;
                    }
                }).filter(href => href !== null);
            }''')
            
            print(f"Raw links found: {len(links)}")
            
            # Filter and clean links
            internal_links = {
                url for url in links 
                if self.is_same_domain(url) 
                and not url.endswith(('.pdf', '.jpg', '.png', '.gif'))
                and '#' not in url
            }
            
            print(f"Internal links found: {len(internal_links)}")
            if len(internal_links) == 0:
                print("Domain check using:", self.base_domain)
                print("Sample URLs being checked:", links[:5])
            
            # Add to collections
            self.found_urls.add(start_url)
            self.found_urls.update(internal_links)
            self.visited_urls.add(start_url)
            
            print(f"\nTotal unique URLs found: {len(self.found_urls)}")
            
            if len(self.found_urls) < max_pages:
                self.to_visit.extend(internal_links - self.visited_urls)
                print(f"Added {len(self.to_visit)} URLs to visit queue")
            
            # Continue with subpage visits...
            while len(self.found_urls) < max_pages and self.to_visit:
                next_url = self.to_visit.popleft()
                if next_url in self.visited_urls:
                    continue
                
                print(f"\nVisiting subpage: {next_url}")
                try:
                    await page.goto(next_url, timeout=30000)
                    await page.wait_for_load_state('domcontentloaded')
                    subpage_links = await self.extract_links(page)
                    self.found_urls.update(subpage_links)
                    self.visited_urls.add(next_url)
                    self.to_visit.extend(subpage_links - self.visited_urls)
                except Exception as e:
                    print(f"Error visiting {next_url}: {str(e)}")
            
            result_urls = list(self.found_urls)[:max_pages]
            print(f"\nFound {len(result_urls)} unique pages to analyze")
            return result_urls
            
        except Exception as e:
            print(f"Error processing homepage: {str(e)}")
            return []