from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import json
from typing import Dict, Set, List
from collections import defaultdict
from .storage_monitor import StorageMonitor  # Import the new class

class NetworkMonitor:
    def __init__(self):
        self.requests = []
        self.domains_contacted = set()
        self.storage_monitor = StorageMonitor()  # Use the imported class
        self.cookies_by_visit = {}
        # Track cookie operations per visit
        self.cookie_stats = defaultdict(lambda: {
            'created': 0,
            'deleted': 0,
            'modified': 0,
            'cookies_seen': set()  # Track unique cookies we've seen
        })

    def _count_request_types(self):
        """Count requests by type"""
        type_counts = defaultdict(int)
        for request in self.requests:
            req_type = request.get('type', 'unknown')
            type_counts[req_type] += 1
        return dict(type_counts)

    def get_cookies(self):
        """Get cookies collected during visits"""
        return self.cookies_by_visit

    def get_cookie_stats(self):
        """Get statistics about cookie operations during visits"""
        stats = {}
        for visit, data in self.cookie_stats.items():
            stats[visit] = {
                'total_unique_cookies': len(data['cookies_seen']),
                'cookies_created': data['created'],
                'cookies_deleted': data['deleted'],
                'cookies_modified': data['modified']
            }
        return stats

    def get_storage_data(self):
        """Get storage monitoring data"""
        return self.storage_monitor.get_results()

    def get_network_data(self):
        """Get network request data"""
        return {
            'requests': self.requests,
            'domains_contacted': list(self.domains_contacted)
        }

    def get_results(self):
        """Get comprehensive monitoring results"""
        return {
            'network_data': self.get_network_data(),
            'statistics': self.get_statistics()
        }

    async def setup_monitoring(self, page, visit_number=0):
        """Setup network monitoring"""
        print(f"Starting network monitor for visit {visit_number}")
        
        # Capture all browser cookies at the end of page load
        async def capture_cookies():
            current_cookies = await page.context.cookies()
            
            if visit_number not in self.cookies_by_visit:
                # First page load in this visit
                self.cookies_by_visit[visit_number] = current_cookies
                self.cookie_stats[visit_number]['created'] = len(current_cookies)
                self.cookie_stats[visit_number]['cookies_seen'].update(c['name'] for c in current_cookies)
            else:
                # Compare with previous state
                previous_cookies = {c['name']: c for c in self.cookies_by_visit[visit_number]}
                current_cookie_dict = {c['name']: c for c in current_cookies}
                
                # Check for new cookies
                new_cookies = set(current_cookie_dict.keys()) - set(previous_cookies.keys())
                self.cookie_stats[visit_number]['created'] += len(new_cookies)
                
                # Check for deleted cookies
                deleted_cookies = set(previous_cookies.keys()) - set(current_cookie_dict.keys())
                self.cookie_stats[visit_number]['deleted'] += len(deleted_cookies)
                
                # Check for modified cookies
                for name in set(previous_cookies.keys()) & set(current_cookie_dict.keys()):
                    if previous_cookies[name]['value'] != current_cookie_dict[name]['value']:
                        self.cookie_stats[visit_number]['modified'] += 1
                
                # Update current state
                self.cookies_by_visit[visit_number] = current_cookies
                self.cookie_stats[visit_number]['cookies_seen'].update(c['name'] for c in current_cookies)
            
        # Capture cookies after each navigation
        page.on('load', lambda: capture_cookies())
        
        async def handle_request(route, request):
            url = request.url
            domain = self._extract_domain(url)
            
            # Record detailed request info
            request_data = {
                "url": url,
                "domain": domain,
                "type": request.resource_type,  # Changed from 'unknown' to actual resource_type
                "resource_type": request.resource_type,
                "method": request.method,
                "headers": dict(request.headers),
                "timestamp": datetime.now().isoformat(),
                "visit_number": visit_number,
                "post_data": request.post_data,
                "frame_url": request.frame.url if request.frame else None,
                "is_navigation": request.is_navigation_request()
            }
            
            self.requests.append(request_data)
            self.domains_contacted.add(domain)
            
            try:
                response = await route.fetch()
                
                # Capture response data
                response_data = {
                    "status": response.status,
                    "status_text": response.status_text,
                    "headers": dict(response.headers),
                    "security_details": {
                        "protocol": response.security_details.protocol if response.security_details else None,
                        "subjectName": response.security_details.subject_name if response.security_details else None
                    }
                }
                
                # Add response data to request record
                request_data["response"] = response_data
                
                # Optionally capture response body for certain content types
                if request.resource_type in ['xhr', 'fetch'] and 'json' in response.headers.get('content-type', ''):
                    try:
                        body = await response.body()
                        request_data["response"]["body"] = body.decode('utf-8')
                    except Exception as e:
                        request_data["response"]["body_error"] = str(e)
                
                await route.fulfill(response=response)
                
            except Exception as e:
                request_data["error"] = str(e)
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
    
    def get_statistics(self):
        """Get comprehensive statistics"""
        return {
            'total_requests': len(self.requests),
            'request_types': self._count_request_types(),
            'cookie_operations': self.get_cookie_stats()
        }

    def finalize_visit(self, visit_number):
        """Store the final state of cookies for this visit"""
        if visit_number in self.cookies_by_visit:
            del self.cookies_by_visit[visit_number]
