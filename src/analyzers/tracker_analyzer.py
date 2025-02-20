from managers.ghostery_manager import GhosteryManager
from typing import Dict

class TrackerAnalyzer:
    def __init__(self):
        self.ghostery = GhosteryManager()

    def analyze_site_data(self, site_data: Dict) -> Dict:
        """Analyze site data for tracking and CNAME cloaking"""
        tracking_stats = {
            'total_tracked': 0,
            'categories': {},
            'organizations': {},
            'cname_cloaking': []
        }

        # Analyze each request in the site data
        for page_data in site_data['pages'].values():
            for request in page_data['requests']:
                tracking_info = self.ghostery.analyze_request(request['url'])
                
                if tracking_info['is_tracker']:
                    tracking_stats['total_tracked'] += 1
                    
                    # Update category stats
                    if tracking_info['category']:
                        tracking_stats['categories'][tracking_info['category']] = \
                            tracking_stats['categories'].get(tracking_info['category'], 0) + 1
                    
                    # Update organization stats
                    if tracking_info['organization']:
                        tracking_stats['organizations'][tracking_info['organization']] = \
                            tracking_stats['organizations'].get(tracking_info['organization'], 0) + 1
                    
                    # Store detailed info for CNAME analysis
                    tracking_stats['cname_cloaking'].append({
                        'url': request['url'],
                        'page_url': request['page_url'],
                        'organization': tracking_info['organization'],
                        'category': tracking_info['category']
                    })

        return tracking_stats 