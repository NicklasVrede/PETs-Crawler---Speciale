from managers.ghostery_manager import GhosteryManager
from typing import Dict

class SourceIdentifier:
    def __init__(self):
        self.ghostery = GhosteryManager()

    def identify_site_sources(self, site_data: Dict) -> Dict:
        """Identify sources of URLs and potential source masking"""
        source_analysis = {
            'total_analyzed': 0,
            'source_categories': {},
            'source_owners': {},
            'masked_sources': []  # Previously cname_cloaking
        }

        # Analyze each request in the site data
        for page_data in site_data['pages'].values():
            for request in page_data['requests']:
                tracking_info = self.ghostery.analyze_request(request['url'])
                
                if tracking_info['is_tracker']:
                    source_analysis['total_analyzed'] += 1
                    
                    # Update category stats
                    if tracking_info['category']:
                        source_analysis['source_categories'][tracking_info['category']] = \
                            source_analysis['source_categories'].get(tracking_info['category'], 0) + 1
                    
                    # Update organization stats
                    if tracking_info['organization']:
                        source_analysis['source_owners'][tracking_info['organization']] = \
                            source_analysis['source_owners'].get(tracking_info['organization'], 0) + 1
                    
                    # Store detailed info for CNAME analysis
                    source_analysis['masked_sources'].append({
                        'url': request['url'],
                        'page_url': request['page_url'],
                        'organization': tracking_info['organization'],
                        'category': tracking_info['category']
                    })

        return source_analysis 