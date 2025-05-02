from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import json
import base64
from typing import Dict, Set, List
from collections import defaultdict
import asyncio
import tqdm

class NetworkMonitor:
    def __init__(self, verbose=False):
        self.requests = []
        self.domains_contacted = set()
        self.cookies_by_visit = {}
        self.verbose = verbose
        
        # Track cookie operations per visit
        self.cookie_stats = defaultdict(lambda: {
            'created': 0,
            'deleted': 0,
            'modified': 0,
            'cookies_seen': set(),
            'cookies_deleted': set()
        })
        self._route_handler_ref = None
        self._load_handler_ref = None

    def _log(self, message):
        if self.verbose:
            tqdm.write(f"  [NetworkMonitor] {message}")

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
        return {}

    def get_results(self):
        """Get comprehensive monitoring results (only public method needed for data retrieval)"""
        return {
            'network_data': self._get_network_data(),
            'statistics': self.get_statistics()
        }

    async def setup_monitoring(self, page, visit_number=0):
        """Setup network monitoring for a new page/visit"""
        self._log(f"Starting network monitor for visit {visit_number}")
        
        async def capture_cookies_handler():
            try:
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
            
            except Exception as e:
                self._log(f"Warning: Error capturing cookies: {e}")

        async def route_handler(route):
            request = route.request
            try:
                url = request.url
                domain = self._extract_domain(url)
                
                # Record detailed request info
                request_data = {
                    "url": url,
                    "domain": domain,
                    "type": request.resource_type,
                    "resource_type": request.resource_type,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "timestamp": datetime.now().isoformat(),
                    "visit_number": visit_number,
                    "post_data": None,  # Default to None
                    "frame_url": request.frame.url if request.frame else None,
                    "is_navigation": request.is_navigation_request()
                }
                
                # Safely handle post data
                if request.method == "POST":
                    try:
                        post_data = request.post_data
                        request_data["post_data"] = post_data
                    except UnicodeDecodeError:
                        request_data["post_data"] = "[BINARY_DATA]"
                    except Exception as e:
                        if "Request context is missing" not in str(e):
                            request_data["post_data"] = f"[ERROR accessing post_data: {str(e)}]"
                        else:
                            request_data["post_data"] = "[INFO: Request context missing, likely during teardown]"
                
                self.requests.append(request_data)
                self.domains_contacted.add(domain)
                
                # Handle response
                try:
                    response = await route.fetch()
                    
                    # Capture response data
                    response_data = {
                        "status": response.status,
                        "status_text": response.status_text,
                        "headers": dict(response.headers),
                        "security_details": None
                    }
                    sec_details = response.security_details
                    if sec_details:
                        response_data["security_details"] = {
                            "protocol": sec_details.protocol,
                            "subjectName": sec_details.subject_name
                        }
                    
                    if self.requests:
                        self.requests[-1]["response"] = response_data
                        
                        if request.resource_type in ['xhr', 'fetch'] and 'json' in response.headers.get('content-type', ''):
                            try:
                                body = await response.body()
                                self.requests[-1]["response"]["body"] = body.decode('utf-8')
                            except Exception as e:
                                self.requests[-1]["response"]["body_error"] = str(e)
                    
                    await route.fulfill(response=response)
                    
                except Exception as e:
                    if "Request context is missing" not in str(e) and "Target page, context or browser has been closed" not in str(e):
                        error_msg = f"Error fetching/fulfilling response for {url}: {str(e)}"
                        self._log(f"  [NetworkMonitor] {error_msg}")
                        if self.requests:
                            self.requests[-1]["error"] = error_msg
                        await route.continue_()
                    else:
                        await route.continue_()
            
            except Exception as e:
                if "Request context is missing" not in str(e) and "Target page, context or browser has been closed" not in str(e):
                    self._log(f"Unexpected error in route_handler for {request.url if request else 'unknown URL'}: {e}")
                try:
                    await route.continue_()
                except Exception:
                    pass

        self._route_handler_ref = route_handler
        self._load_handler_ref = capture_cookies_handler

        try:
            await page.route("**", self._route_handler_ref)
        except Exception as e:
            tqdm.write(f"  [NetworkMonitor] Warning: Failed to set up routing: {e}")

        try:
            page.on('load', self._load_handler_ref)
        except Exception as e:
            tqdm.write(f"  [NetworkMonitor] Warning: Failed to set up load listener: {e}")

    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url.split('/')[2] if '://' in url else url.split('/')[0]
    
    def get_statistics(self):
        """Get computed statistics from network data (private)"""
        return {
            'total_requests': len(self.requests),
            'request_types': self._count_request_types(),
            'cookie_operations': self.get_cookie_stats()
        }
    
    def _get_network_data(self):
        """Get raw network request data (private)"""
        return {
            'requests': self.requests,
            'domains_contacted': list(self.domains_contacted)
        }

    async def teardown_monitoring(self, page):
        """Remove event listeners and route handlers added during setup."""
        # Check if the reference exists before attempting to remove
        if self._route_handler_ref:
            try:
                # Attempt to remove the specific route handler
                await page.unroute("**", handler=self._route_handler_ref)
                self._log("Successfully unrouted handler.")
            except Exception as e:
                # Log errors unless they are expected ones during page/context closure
                if "Target page" not in str(e) and "context" not in str(e):
                    tqdm.write(f"  [NetworkMonitor] Warning: Error unrouting handler: {e}")
            finally:
                # Always clear the reference to prevent potential issues
                self._route_handler_ref = None

        # check if the load handler ref exists before attempting to remove
        if self._load_handler_ref:
            try:
                # Attempt to remove the specific load listener
                page.remove_listener("load", self._load_handler_ref)
                self._log("Successfully removed load listener.")
            except Exception as e:
                # Log errors unless they are expected ones during page/context closure
                if "Target page" not in str(e) and "context" not in str(e):
                    tqdm.write(f"  [NetworkMonitor] Warning: Error removing load listener: {e}")
            finally:
                # Always clear the reference
                self._load_handler_ref = None