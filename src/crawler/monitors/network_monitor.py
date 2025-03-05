from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import json
from typing import Dict, Set, List

class StorageMonitor:
    """Monitor web storage (localStorage and sessionStorage)"""
    def __init__(self):
        self.storage_data = []
        
    async def capture_snapshot(self, page, visit_number):
        """Capture current state of web storage with visit number"""
        storage_data = await page.evaluate("""() => {
            return {
                localStorage: Object.entries(localStorage).map(([key, value]) => ({
                    key, value
                })),
                sessionStorage: Object.entries(sessionStorage).map(([key, value]) => ({
                    key, value
                }))
            }
        }""")
        
        # Add metadata to each storage item
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'url': page.url,
            'visit_number': visit_number,
            'localStorage': storage_data['localStorage'],
            'sessionStorage': storage_data['sessionStorage']
        }
        
        self.storage_data.append(snapshot)
        
    def get_results(self):
        """Get all storage data organized by visit"""
        return self.storage_data

class NetworkMonitor:
    def __init__(self):
        self.requests = []
        self.cookies_set = []
        self.domains_contacted = set()
        self.storage_monitor = StorageMonitor()
        
    async def setup_monitoring(self, page, visit_number=0):
        """Setup network monitoring"""
        print(f"Starting network monitor for visit {visit_number}")
        
        async def handle_request(route, request):
            url = request.url
            domain = self._extract_domain(url)
            
            # Record basic request info
            request_data = {
                "url": url,
                "domain": domain,
                "resource_type": request.resource_type,
                "timestamp": datetime.now().isoformat(),
                "visit_number": visit_number
            }
            
            self.requests.append(request_data)
            self.domains_contacted.add(domain)
            
            try:
                response = await route.fetch()
                
                # Track cookies
                if "set-cookie" in response.headers:
                    self.cookies_set.append({
                        "domain": domain,
                        "cookie": response.headers["set-cookie"],
                        "url": url,
                        "visit_number": visit_number,
                        "timestamp": datetime.now().isoformat()
                    })
                
                await route.fulfill(response=response)
                
            except Exception as e:
                try:
                    await route.continue_()
                except:
                    pass

        # Monitor ALL network requests
        await page.route("**", lambda route: handle_request(route, route.request))
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url.split('/')[2] if '://' in url else url.split('/')[0]
    
    def get_results(self):
        """Get all monitoring results"""
        return {
            'requests': self.requests,
            'cookies_set': self.cookies_set,
            'domains_contacted': list(self.domains_contacted),
            'storage': self.storage_monitor.get_results()
        }
    
    def get_statistics(self):
        """Get basic request statistics"""
        stats = {
            'total_requests': len(self.requests),
            'request_types': {},
            'domains': {},
            'total_cookies': len(self.cookies_set)
        }
        
        for req in self.requests:
            # Count request types
            req_type = req['resource_type']
            stats['request_types'][req_type] = stats['request_types'].get(req_type, 0) + 1
            
            # Count domains
            domain = req['domain']
            stats['domains'][domain] = stats['domains'].get(domain, 0) + 1
        
        return stats

    def analyze_cookie_persistence(self, visit_results):
        """Analyze which cookies persist across visits"""
        persistent_cookies = []
        cookie_values_by_visit = {}
        
        # Collect cookie values from each visit
        for visit in visit_results:
            visit_num = visit['visit_number']
            visit_cookies = visit['network'].get('cookies_set', [])
            cookie_values_by_visit[visit_num] = {
                self._parse_cookie_value(cookie['cookie']): cookie
                for cookie in visit_cookies
            }
        
        # Find cookies that appear in all visits
        if len(cookie_values_by_visit) > 1:
            first_visit_cookies = cookie_values_by_visit[0]
            
            for cookie_value, cookie_data in first_visit_cookies.items():
                appears_in_all_visits = True
                
                # Check if cookie appears in subsequent visits
                for visit_num in range(1, len(cookie_values_by_visit)):
                    if cookie_value not in cookie_values_by_visit[visit_num]:
                        appears_in_all_visits = False
                        break
                
                if appears_in_all_visits and len(cookie_value) >= 8:  # Only track cookies with sufficient length
                    persistent_cookies.append({
                        'cookie': cookie_data,
                        'persistence': 'across_visits',
                        'visits_found': list(cookie_values_by_visit.keys()),
                        'length': len(cookie_value)
                    })
        
        return persistent_cookies

    def _parse_cookie_value(self, cookie_header: str) -> str:
        """Extract the value from a Set-Cookie header"""
        try:
            # Get the main part before any attributes
            main_part = cookie_header.split(';')[0]
            # Get the value after the first =
            value = main_part.split('=', 1)[1]
            return value
        except:
            return ""