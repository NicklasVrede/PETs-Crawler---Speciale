from datetime import datetime
from typing import Dict, List, Set, Counter
from collections import defaultdict, Counter
from urllib.parse import urlparse
from pathlib import Path

class FingerprintCollector:
    def __init__(self, verbose=False):
        # Track data separately for each visit
        self.visits_data = {}
        self.current_visit = 0
        self.verbose = verbose
        
        # Keep the script patterns global
        self.script_patterns = {}
        
        # Load the JavaScript file
        script_path = Path(__file__).parent / "fingerprint_collector.js"
        with open(script_path, 'r') as f:
            self.monitor_js = f.read()

    async def setup_monitoring(self, page, visit_number=0):
        """Setup monitoring before page loads"""
        if self.verbose:
            print(f"Setting up fingerprint collection for visit #{visit_number+1}...")
        self.current_visit = visit_number
        
        # Initialize data structure for this visit if it doesn't exist
        if visit_number not in self.visits_data:
            self.visits_data[visit_number] = {
                'page_data': defaultdict(lambda: {
                    'api_counts': Counter(),
                    'categories': Counter(),
                }),
                'category_counts': Counter()
            }

        # Replace the visit number placeholder in the JavaScript
        js_code = self.monitor_js.replace('VISIT_NUMBER', str(visit_number))

        # Inject our monitoring code
        await page.add_init_script(js_code)

        # Setup callback from JavaScript
        await page.expose_function('reportFPCall', self._handle_fp_call)

    def _normalize_url(self, url):
        """Normalize URL by removing parameters"""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except:
            return url

    async def _handle_fp_call(self, call_data):
        """Process fingerprinting API calls with aggregation"""
        category = call_data['category']
        api = call_data['api']
        url = self._normalize_url(call_data['url'])
        visit = call_data.get('visit', self.current_visit)
        
        # Make sure this visit exists in our data structure
        if visit not in self.visits_data:
            self.visits_data[visit] = {
                'page_data': defaultdict(lambda: {
                    'api_counts': Counter(),
                    'categories': Counter(),
                }),
                'category_counts': Counter()
            }
        
        # Get the data for this visit
        visit_data = self.visits_data[visit]
        
        # Increment API call count for this page
        visit_data['page_data'][url]['api_counts'][api] += 1
        
        # Increment category count for this page
        visit_data['page_data'][url]['categories'][category] += 1
        
        # Update global category counts for this visit
        visit_data['category_counts'][category] += 1

    def _get_results_for_visit(self, visit_number):
        """Get fingerprinting results for a specific visit"""
        # If this visit doesn't exist in our data, create an empty structure
        if visit_number not in self.visits_data:
            print(f"Warning: No fingerprinting data for visit {visit_number}, creating empty result")
            self.visits_data[visit_number] = {
                'page_data': defaultdict(lambda: {
                    'api_counts': Counter(),
                    'categories': Counter(),
                }),
                'category_counts': Counter()
            }
        
        visit_data = self.visits_data[visit_number]
        page_data = visit_data['page_data']
        category_counts = visit_data['category_counts']
        
        # Aggregate API calls at the domain level
        domain_api_counts = Counter()
        domain_category_counts = Counter()
        
        for url, data in page_data.items():
            domain = urlparse(url).netloc
            domain_api_counts.update(data['api_counts'])
            domain_category_counts.update(data['categories'])
        
        # Calculate total calls
        total_calls = sum(domain_api_counts.values())
        
        # Create technique breakdown by aggregating categories
        technique_breakdown = {
            'canvas': domain_category_counts.get('canvas', 0),
            'webgl': domain_category_counts.get('webgl', 0) + domain_category_counts.get('webgl2', 0),
            'audio': domain_category_counts.get('audio', 0),
            'hardware': domain_category_counts.get('hardware', 0) + domain_category_counts.get('sensor', 0),
            'fonts': domain_category_counts.get('fonts', 0),
            'navigator': domain_category_counts.get('navigator', 0),
            'storage': domain_category_counts.get('storage', 0),
            'screen': domain_category_counts.get('screen', 0),
            'window': domain_category_counts.get('window', 0),
            'date': domain_category_counts.get('date', 0),
            'media': domain_category_counts.get('media', 0),
            'dom': domain_category_counts.get('dom', 0),
            'performance': domain_category_counts.get('performance', 0),
            'speech': domain_category_counts.get('speech', 0),
            'intl': domain_category_counts.get('intl', 0),
            'webrtc': domain_category_counts.get('webrtc', 0),
            'permission': domain_category_counts.get('permission', 0)
        }
        
        # Remove techniques with zero counts
        technique_breakdown = {k: v for k, v in technique_breakdown.items() if v > 0}
        
        return {
            'visit_number': visit_number,
            'domain_summary': {
                'total_calls': total_calls,
                'technique_breakdown': technique_breakdown,
                'api_breakdown': dict(domain_api_counts)
            }
        }
    
    def _get_combined_results(self):
        """Get combined fingerprinting results across all visits"""
        # Combined data structures
        all_techniques = set()
        all_category_counts = Counter()
        total_calls = 0
        pages_analyzed = set()
        
        # Per-visit summaries
        visit_summaries = []
        
        # Per-visit page summaries
        visit_page_summaries = {}  # Will store page summaries by visit
        
        # Process each visit
        for visit_number, visit_data in self.visits_data.items():
            # Initialize page summaries for this visit
            visit_page_summaries[visit_number] = []
            
            # Get visit-specific results
            visit_result = self._get_results_for_visit(visit_number)
            
            # Add to visit summaries
            visit_summaries.append({
                'visit_number': visit_number,
                'total_calls': visit_result['domain_summary']['total_calls']
            })
            
            # Store page summaries for this visit
            visit_page_summaries[visit_number] = visit_result['domain_summary']
            
            # Update combined data
            all_techniques.update(visit_result['technique_breakdown'].keys())
            all_category_counts.update(visit_result['technique_breakdown'])
            total_calls += visit_result['domain_summary']['total_calls']
            
            # Add tracked pages to the set
            pages_analyzed.update(visit_data['page_data'].keys())
        
        # Create final result
        result = {
            'techniques_detected': list(all_techniques),
            'visit_summaries': visit_summaries,
            'summary': {
                'total_calls': total_calls,
                'total_visits': len(self.visits_data),
                'pages_analyzed': len(pages_analyzed),
                'category_counts': dict(all_category_counts)
            },
            'visit_page_data': {}  # New field for per-visit page data
        }
        
        # Add per-visit page summaries
        for visit_number, page_summary in visit_page_summaries.items():
            result['visit_page_data'][str(visit_number)] = page_summary
        
        return result

    def get_fingerprinting_data(self):
        """Get fingerprinting results per visit"""
        # Return only the visits data
        return {
            visit: self._get_results_for_visit(visit) 
            for visit in self.visits_data.keys()
        }