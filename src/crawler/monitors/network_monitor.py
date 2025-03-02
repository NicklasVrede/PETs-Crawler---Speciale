from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

class NetworkMonitor:
    def __init__(self):
        self.requests = []
        self.current_page = None
        self.script_metadata = []

    def _format_url_for_print(self, url):
        """Format URL to show only domain and truncated path"""
        parsed = urlparse(url)
        path = parsed.path[:30] + '...' if len(parsed.path) > 30 else parsed.path
        return f"{parsed.netloc}{path}"

    async def setup_monitoring(self, page):
        """Setup network monitoring for a page"""
        print("Starting network monitor")
        
        # Track page changes first
        async def handle_navigation(frame):
            if frame == page.main_frame:
                self.current_page = frame.url
        
        page.on("framenavigated", handle_navigation)
        
        # Monitor all requests including subresources
        async def handle_request(route, request):
            request_data = {
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'timestamp': datetime.now(),
                'resource_type': request.resource_type,
                'is_navigation': request.is_navigation_request(),
                'page_url': self.current_page or request.url,
                'post_data': request.post_data
            }
            
            try:
                # Only fetch response for scripts
                if request.resource_type == 'script':
                    response = await route.fetch()
                    request_data['response'] = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'body': await response.text()
                    }
                    # Add script metadata
                    self.script_metadata.append({
                        'url': request.url,
                        'page_url': self.current_page,
                        'timestamp': datetime.now().isoformat()
                    })
                    await route.fulfill(response=response)
                else:
                    await route.continue_()
                    
            except Exception as e:
                try:
                    await route.continue_()
                except:
                    pass
            
            self.requests.append(request_data)

        # Monitor ALL network requests
        await page.route("**", lambda route: handle_request(route, route.request))

    def get_results(self):
        """Get all collected network monitoring results"""
        return {
            'requests': self.requests,
            'script_metadata': self.script_metadata
        }

    def get_statistics(self):
        """Get basic request statistics"""
        stats = {
            'total_requests': len(self.requests),
            'request_types': {},
            'total_cookies': 0
        }
        
        for req in self.requests:
            # Count request types
            req_type = req['resource_type']
            stats['request_types'][req_type] = stats['request_types'].get(req_type, 0) + 1
            
            # Count cookies
            headers = req.get('headers', {})
            if 'cookie' in headers:
                stats['total_cookies'] += len(headers['cookie'].split(';'))
        
        return stats