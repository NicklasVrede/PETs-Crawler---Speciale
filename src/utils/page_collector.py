import asyncio
import json
import os
import csv
from urllib.parse import urlparse
from collections import deque
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import os
from tqdm import tqdm

if __name__ == "__main__":
    from util import construct_paths, load_config, get_profile_config
else:
    from utils.util import construct_paths, load_config, get_profile_config

class PageCollector:
    def __init__(self, base_domain, verbose=False):
        # Strip 'www.' if present in the base domain
        self.base_domain = base_domain.lower().replace('www.', '')
        self.visited_urls = set()
        self.to_visit = deque()
        self.found_urls = []  # Use list to maintain order
        self.progress_bar = None
        self.verbose = verbose

    def _log(self, message):
        if self.verbose:
            tqdm.write(message)

    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            # Strip 'www.' from the netloc for comparison
            domain = parsed.netloc.lower().replace('www.', '')
            
            # Check if it's the same domain OR if it's a subdomain
            return domain == self.base_domain or domain.endswith('.' + self.base_domain)
        except Exception as e:
            tqdm.write(f"Error parsing URL {url}: {e}")
            return False

    async def extract_links(self, page):
        """Extract all links from the current page"""
        # First try: get all links, even if not visible
        all_links = await page.evaluate('''() => {
            const links = document.querySelectorAll('a[href]');
            return Array.from(links).map(link => link.href);
        }''')
        
        # Log the raw links found by the first evaluate call
        self._log(f"Raw links found (before visibility/domain check): {len(all_links)}")
        if self.verbose and len(all_links) < 20: # Log first few if list is short
             self._log(f"Raw links sample: {all_links[:20]}")
        
        # Then try with visibility check but make it less strict
        visible_links = await page.evaluate('''() => {
            // More lenient visibility check
            function isVisible(elem) {
                if (!elem) return false;
                
                // Check only essential display properties
                const style = window.getComputedStyle(elem);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    return false;
                }
                
                // Don't check dimensions or position - too restrictive
                
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
        
        # Log the raw visible links found
        self._log(f"Raw visible links found (before domain check): {len(visible_links)}")
        if self.verbose and len(visible_links) < 20: # Log first few if list is short
             self._log(f"Raw visible links sample: {visible_links[:20]}")

        # Filter and clean links
        internal_links = set()
        # Prioritize visible links if available
        links_to_filter = visible_links if len(visible_links) > 0 else all_links
        
        for url in links_to_filter:
            if self.is_same_domain(url):
                internal_links.add(url)
        
        # If no internal links found using the primary list, try the other one as fallback
        if len(internal_links) == 0 and links_to_filter is visible_links and len(all_links) > 0:
             self._log("No internal links in visible set, trying fallback with all_links")
             for url in all_links:
                 if self.is_same_domain(url):
                     internal_links.add(url)

        # Simplified logging based on final internal_links count
        if len(internal_links) == 0:
            self._log(f"Found 0 internal links matching domain '{self.base_domain}'")
        else:
            self._log(f"Found {len(internal_links)} internal links matching domain '{self.base_domain}'")
        
        return internal_links

    async def collect_pages(self, page, max_pages=40, homepage_links=10, output_dir="data/site_pages_Trial100"):
        """
        Collect subpages from a website by exploring chains of links from the homepage
        
        Args:
            page: Playwright page object
            max_pages: Maximum pages to collect in total
            homepage_links: Not used in this simplified implementation
        """
        # Initialize progress bar
        self.progress_bar = tqdm(total=max_pages, desc="Collecting URLs", unit="page")
        
        # Store HTTP status for later reporting
        self.http_status = None
        
        try:
            # Start with the homepage
            homepage_url = f"https://{self.base_domain}/"
            
            # Visit homepage with better error handling
            try:
                # Increased timeout for initial potentially slow load or redirect
                response = await page.goto(homepage_url, timeout=90000) 
                # Store the HTTP status code
                if response:
                    self.http_status = response.status
                    if response.status >= 400:
                        self._log(f"Homepage returned HTTP error: {response.status}")
                
                # Wait for the basic document structure to be ready
                self._log(f"Waiting for DOM content loaded...")
                await page.wait_for_load_state('domcontentloaded', timeout=15000) 
                
                # Update the base domain based on the final URL after redirect
                final_url = page.url
                parsed_final = urlparse(final_url)
                final_domain = parsed_final.netloc.lower().replace('www.', '')
                
                if final_domain != self.base_domain:
                    tqdm.write(f"Detected redirect: {self.base_domain} -> {final_domain}")
                    self.base_domain = final_domain
                    homepage_url = final_url  # Update homepage URL too
                    # Add an explicit wait after redirect detection for JS etc. to potentially run
                    self._log(f"Waiting after redirect before extracting links...")
                    await page.wait_for_timeout(3000) # Wait 3 seconds

                # Try waiting for network idle again, more forgiving timeout
                try:
                    self._log(f"Attempting networkidle wait before link extraction...")
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception as e:
                    # Don't print this message - too common and expected
                    self._log(f"Networkidle timed out before link extraction, proceeding anyway.")
                    pass
                
            except Exception as e:
                tqdm.write(f"Failed to load homepage {homepage_url}: {e}")
                self.progress_bar.close()
                return []
            
            # Add homepage as first URL
            self.found_urls.append(homepage_url)
            self.visited_urls.add(homepage_url)
            self.progress_bar.update(1)
            
            # Get all links from the homepage (hopefully page is more ready now)
            homepage_links_list = list(await self.extract_links(page))
            self._log(f"Found {len(homepage_links_list)} links on homepage")

            # Check if homepage link extraction failed
            if len(homepage_links_list) == 0:
                self._log(f"Homepage link extraction failed for {homepage_url}. Saving HTML for inspection.")
                try:
                    html_content = await page.content()
                    # Create a safe filename using the current base_domain
                    safe_debug_domain = self.base_domain.replace('.', '_').replace('/','_') 
                    debug_filename = f"debug_html_{safe_debug_domain}.html"
                    # Ensure output_dir exists before trying to save
                    os.makedirs(output_dir, exist_ok=True) 
                    debug_filepath = os.path.join(output_dir, debug_filename) 
                    with open(debug_filepath, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    self._log(f"Saved HTML to {debug_filepath}")
                except Exception as html_err:
                    self._log(f"Could not save debug HTML: {html_err}")
                
                # If homepage fails, we cannot proceed. Close progress and return empty.
                tqdm.write(f"Stopping collection for {self.base_domain} due to homepage link extraction failure.")
                self.progress_bar.close()
                return []
            
            # Keep track of homepage links we've tried as starting points
            homepage_links_tried = []
            
            while len(self.found_urls) < max_pages:
                # Find a homepage link we haven't tried as a chain start
                chain_start = None
                for link in homepage_links_list:
                    if link != homepage_url and link not in homepage_links_tried:
                        chain_start = link
                        homepage_links_tried.append(link)
                        break
                
                # If no more homepage links to try, we're done
                if not chain_start:
                    break
                
                # Start exploring this chain
                self._log(f"Starting new chain from: {chain_start}")
                current_url = chain_start
                
                # Follow the chain until it ends
                chain_continues = True
                while chain_continues and len(self.found_urls) < max_pages:
                    try:
                        # If we haven't visited this URL before, add it to our collection
                        if current_url not in self.visited_urls and current_url not in self.found_urls:
                            self.found_urls.append(current_url)
                            self.progress_bar.update(1)
                        
                        # Visit the current URL with improved error handling
                        try:
                            # Increased timeout and don't wait for networkidle which is prone to timeouts
                            response = await page.goto(current_url, wait_until='domcontentloaded', timeout=8000)
                            # Check if we got an HTTP error
                            if response and response.status >= 400:
                                self._log(f"Page returned HTTP error: {response.status} for {current_url}")
                            await page.wait_for_timeout(2000)  # Simple delay instead of waiting for networkidle
                        except Exception as e:
                            tqdm.write(f"Error loading page {current_url}: {e}")
                            # Mark as visited even if it failed, so we don't retry
                            self.visited_urls.add(current_url)
                            chain_continues = False
                            continue
                        
                        # Mark as visited
                        self.visited_urls.add(current_url)
                        
                        # Get links from this page
                        page_links = list(await self.extract_links(page))
                        
                        # Find next unvisited link
                        next_link = None
                        for link in page_links:
                            if link not in self.visited_urls:
                                next_link = link
                                break
                        
                        if next_link:
                            current_url = next_link
                        else:
                            # Chain has ended, go back to homepage to start a new chain
                            chain_continues = False
                            
                    except Exception as e:
                        tqdm.write(f"Error following chain: {e}")
                        chain_continues = False
            
            # Close the progress bar
            self.progress_bar.close()
            
            # Return collected URLs (up to max_pages)
            result_urls = self.found_urls[:max_pages]
            return result_urls
            
        except Exception as e:
            tqdm.write(f"Error in collect_pages: {e}")
            if self.progress_bar:
                self.progress_bar.close()
            return []


async def collect_site_pages(domain, max_pages=40, homepage_links=3, setup='i_dont_care_about_cookies', chunk_id=0, output_dir="data/site_pages_Trial100"):
    """Run the page collection for a single site"""
    # Load configuration to use the same extension as the main crawler
    config = load_config('config.json')
    profile_config = get_profile_config(config, setup)
    _, full_extension_path = construct_paths(config, setup)
    
    # Verify extension path exists
    if not os.path.exists(full_extension_path):
        tqdm.write(f"ERROR: Extension path does not exist: {full_extension_path}")
        return []
    
    # Initialize Stealth
    stealth = Stealth()

    async with async_playwright() as p:
        try:
            # Launch browser with extension but without user data directory
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    f"--disable-extensions-except={full_extension_path}",
                    f"--load-extension={full_extension_path}",
                    f"--window-name=Browser-Chunk-{chunk_id}"  # Add window name to identify browsers
                ],
                ignore_default_args=["--disable-extensions"],  # Keep extensions enabled
                slow_mo=3000
            )
            
            # Add ignore_https_errors to handle certificate issues
            context = await browser.new_context(
                viewport=profile_config.get('viewport', {'width': 1280, 'height': 800}),
                ignore_https_errors=True  # Ignore SSL certificate errors
            )
            
            # Apply stealth to the context
            await stealth.apply_stealth_async(context)

            # Set a browser title that includes the chunk ID for easier identification
            page = await context.new_page()
            await page.evaluate(f"document.title = 'Browser Chunk {chunk_id} - {domain}'")
            
            collector = PageCollector(domain, verbose=True)
            pages = await collector.collect_pages(page, max_pages, homepage_links, output_dir)
            
            # Return the pages along with the HTTP status if available
            http_status = getattr(collector, 'http_status', None)
            
            await context.close()
            await browser.close()
            return pages, http_status
            
        except Exception as e:
            tqdm.write(f"Failed to launch browser with extension for chunk {chunk_id}: {e}")
            # Try without extension as fallback
            try:
                tqdm.write(f"Attempting to launch without extension as fallback for chunk {chunk_id}...")
                browser = await p.chromium.launch(
                    headless=False,
                    args=[f"--window-name=Browser-Chunk-{chunk_id}-Fallback"]
                )
                # Add ignore_https_errors here too
                context = await browser.new_context(
                    ignore_https_errors=True  # Ignore SSL certificate errors
                )
                
                # Apply stealth to the context in fallback too
                await stealth.apply_stealth_async(context)

                page = await context.new_page()
                await page.evaluate(f"document.title = 'Browser Chunk {chunk_id} (Fallback) - {domain}'")
                
                collector = PageCollector(domain, verbose=True)
                pages = await collector.collect_pages(page, max_pages, homepage_links, output_dir)
                
                # Return the pages along with the HTTP status if available
                http_status = getattr(collector, 'http_status', None)
                
                await context.close()
                await browser.close()
                return pages, http_status
            except Exception as e2:
                tqdm.write(f"Complete failure to collect pages for chunk {chunk_id}: {e2}")
                return [], None


def save_site_pages(domain, pages, output_dir="data/site_pages_Trial100"):
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
    
    tqdm.write(f"Saved {len(pages)} pages for {domain} to {filename}")
    return filename


def load_site_pages(domain, input_dir="data/site_pages_final", count=20):
    """Load collected pages from a JSON file and return the top N"""
    safe_domain = domain.replace(".", "_")
    filename = os.path.join(input_dir, f"{safe_domain}.json")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Get the URLs, limited to count
        pages = data['pages'][:count]
        
        #tqdm.write(f"Loaded top {len(pages)} pages for {domain} from {filename}")
        return pages
    except FileNotFoundError:
        return None


async def collect_site_chunk(domains_chunk, chunk_id, setup, max_pages, homepage_links, insufficient_file, insufficient_domains, overall_progress, output_dir="data/site_pages_Trial100"):
    """Process a chunk of domains with a single browser instance"""
    # Ensure the insufficient file exists with headers if it's new
    if not os.path.exists(insufficient_file):
        with open(insufficient_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['domain', 'rank', 'pages_collected', 'failure_reason', 'http_status'])
    
    for domain_info in domains_chunk:
        # Support both simple domain strings and (domain, rank) tuples
        if isinstance(domain_info, tuple):
            domain, rank = domain_info
        else:
            domain = domain_info
            rank = "unknown"  # Default rank if not provided
            
        # Create safe filename version of the domain for file storage
        safe_domain = domain.replace('.', '_')
        
        # Check if file already exists
        file_path = f"{output_dir}/{safe_domain}.json"
        if os.path.exists(file_path):
            tqdm.write(f"[Chunk {chunk_id}] Skipping {domain} - already processed, in {file_path}")
            overall_progress.update(1)
            continue
        
        # Skip domains with known insufficient pages (just check by domain since we changed the format)
        if safe_domain in insufficient_domains:
            tqdm.write(f"[Chunk {chunk_id}] Skipping {domain} - previously failed to collect enough pages")
            overall_progress.update(1)
            continue
            
        tqdm.write(f"\n{'='*50}")
        tqdm.write(f"[Chunk {chunk_id}] Collecting pages for {domain} (rank: {rank})...")
        tqdm.write(f"{'='*50}")
        
        # Use the original domain format for collection
        start_time = asyncio.get_event_loop().time()
        result = await collect_site_pages(domain, max_pages=max_pages, homepage_links=homepage_links, setup=setup, chunk_id=chunk_id, output_dir=output_dir)
        
        # Unpack the result - now includes HTTP status
        if isinstance(result, tuple) and len(result) == 2:
            pages, http_status = result
        else:
            # Backward compatibility in case the function signature changed
            pages = result
            http_status = None
            
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # Log failure reason for troubleshooting
        if not pages or len(pages) < 20:
            pages_count = len(pages) if pages else 0
            
            # Include HTTP status in failure reason if available
            if http_status is not None and http_status >= 400:
                failure_reason = f"HTTP {http_status}" + (": No pages collected" if pages_count == 0 else f": Only {pages_count} pages (need at least 20)")
            else:
                failure_reason = "No pages collected" if pages_count == 0 else f"Only {pages_count} pages (need at least 20)"
                
            tqdm.write(f"[Chunk {chunk_id}] ✗ {failure_reason} for {domain} (took {elapsed_time:.2f}s)")
            
            # Record domain as having insufficient pages with additional information
            with open(insufficient_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([domain, rank, pages_count, failure_reason, http_status or ''])
        else:
            save_site_pages(domain, pages, output_dir=output_dir)
            tqdm.write(f"[Chunk {chunk_id}] ✓ Saved {len(pages)} pages for {domain} (took {elapsed_time:.2f}s)")
        
        # Update overall progress
        overall_progress.update(1)
        
        # Brief pause between domains to allow resources to be freed
        await asyncio.sleep(1)


async def collect_all_site_pages(setup='i_dont_care_about_cookies', max_pages=40, homepage_links=10, num_browsers=8, domain_path="data/db+ref/study-sites.csv", output_dir="data/site_pages_Trial100"):
    """Collect pages for all domains in study-sites.csv using multiple browser instances"""
    # Load domains from CSV
    domains = []
    try:
        with open(domain_path, 'r') as f:
            reader = csv.DictReader(f)
            # Store domains with their rank if available
            domains = []
            for row in reader:
                domain = row['domain'].lower()
                rank = row.get('rank', 'unknown')
                domains.append((domain, rank))
    except Exception as e:
        tqdm.write(f"Error loading study-sites.csv: {e}")
        return

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create/load list of domains with insufficient pages
    insufficient_domains = set()
    insufficient_file = "data/insufficient_pages_domains.csv"
    os.makedirs(os.path.dirname(insufficient_file), exist_ok=True)
    
    # Modified to handle the new CSV format
    if os.path.exists(insufficient_file):
        try:
            with open(insufficient_file, 'r', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader, None)  # Skip header
                insufficient_domains = set(row[0] for row in reader)
                
                # Check if we need to update the file format to include http_status and remove elapsed_time
                if headers and ('http_status' not in headers or 'elapsed_time' in headers):
                    tqdm.write("Updating insufficient_pages_domains.csv format...")
                    # Read all existing data
                    with open(insufficient_file, 'r', newline='') as f:
                        reader = csv.reader(f)
                        headers = next(reader, None)  # Skip header
                        rows = list(reader)
                    
                    # Write back with new header format
                    with open(insufficient_file, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['domain', 'rank', 'pages_collected', 'failure_reason', 'http_status'])
                        for row in rows:
                            # Create properly formatted row based on old format
                            new_row = [row[0], row[1], row[2]]
                            
                            # Handle case where elapsed_time is present
                            if len(row) >= 5:  # Old format with elapsed_time
                                new_row.append(row[4])  # failure_reason
                                new_row.append(row[5] if len(row) > 5 else '')  # http_status
                            else:
                                new_row.append(row[3] if len(row) > 3 else '')  # failure_reason
                                new_row.append('')  # empty http_status
                                
                            writer.writerow(new_row)
        except Exception as e:
            tqdm.write(f"Error reading insufficient_pages_domains.csv: {e}")
            # If there's an error, create a new file with headers
            with open(insufficient_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['domain', 'rank', 'pages_collected', 'failure_reason', 'http_status'])
    else:
        # Create the file with headers if it doesn't exist
        with open(insufficient_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['domain', 'rank', 'pages_collected', 'failure_reason', 'http_status'])
    
    # Pre-filter domains that have already been processed or have insufficient pages
    unprocessed_domains = []
    for domain_info in domains:
        if isinstance(domain_info, tuple):
            domain, rank = domain_info
        else:
            domain = domain_info
            rank = "unknown"
        
        safe_domain = domain.replace('.', '_')
        file_path = f"{output_dir}/{safe_domain}.json"
        if not os.path.exists(file_path) and safe_domain not in insufficient_domains:
            unprocessed_domains.append((domain, rank))
    
    already_processed = len(domains) - len(unprocessed_domains)
    tqdm.write(f"\nFound {already_processed} already processed domains, {len(unprocessed_domains)} remaining")
    tqdm.write(f"Collecting pages for {len(unprocessed_domains)} domains using {num_browsers} parallel browsers...")
    
    # Create overall progress bar
    overall_progress = tqdm(total=len(domains), desc="Overall Progress", unit="domain", position=0)
    # Update progress for already processed domains
    overall_progress.update(already_processed)
    
    # If there are no unprocessed domains, we're done
    if not unprocessed_domains:
        overall_progress.close()
        tqdm.write("All domains have already been processed!")
        return
    
    # Split unprocessed domains into chunks for parallel processing
    chunk_size = len(unprocessed_domains) // num_browsers
    if len(unprocessed_domains) % num_browsers != 0:
        chunk_size += 1
    
    domain_chunks = [unprocessed_domains[i:i+chunk_size] for i in range(0, len(unprocessed_domains), chunk_size)]
    
    # Start parallel collection processes
    tasks = []
    for i, chunk in enumerate(domain_chunks):
        tqdm.write(f"Browser {i+1} will process {len(chunk)} domains")
        task = collect_site_chunk(chunk, i+1, setup, max_pages, homepage_links, insufficient_file, insufficient_domains, overall_progress, output_dir)
        tasks.append(task)
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks)
    
    # Close progress bar
    overall_progress.close()
    
    tqdm.write("Completed page collection for all domains")


if __name__ == "__main__":
    asyncio.run(collect_all_site_pages(domain_path="data/db+ref/Tranco_final_sample.csv", output_dir="data/site_pages_final")) 