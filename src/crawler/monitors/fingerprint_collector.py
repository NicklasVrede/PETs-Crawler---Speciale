from datetime import datetime
from typing import Dict, List, Set, Counter
from collections import defaultdict, Counter
import json
from urllib.parse import urlparse

class FingerprintCollector:
    def __init__(self, verbose=False):
        # Track data separately for each visit
        self.visits_data = {}
        self.current_visit = 0
        self.verbose = verbose
        
        # Keep the script patterns global
        self.script_patterns = {}

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
                    'scripts': set()
                }),
                'category_counts': Counter()
            }

        # Inject our monitoring code
        await page.add_init_script("""
            window.currentPageIndex = 0;  // Default to 0 for homepage
            window.currentVisitNumber = """ + str(visit_number) + """;  // Set current visit number
            
            window.fpCollector = {
                calls: new Set(),
                scriptSources: new Map(),
                
                // Track script sources
                getScriptSource() {
                    try {
                        const error = new Error();
                        const stack = error.stack || '';
                        // Look for full URLs in the stack trace
                        const urlMatch = stack.match(/at (?:Object\\.|)(?:https?:\\/\\/[^\\s]+|[^\\s:]+)/);
                        if (urlMatch) {
                            // Extract just the URL or script name
                            const source = urlMatch[0].replace('at Object.', '').replace('at ', '');
                            return source;
                        }
                        // If we can't find a URL, try to get the script name
                        const currentScript = document.currentScript;
                        if (currentScript && currentScript.src) {
                            return currentScript.src;
                        }
                    } catch (e) {
                        console.error('Error getting script source:', e);
                    }
                    return 'unknown source';
                },

                // Report API usage to Python
                report(category, api, args = null) {
                    const source = this.getScriptSource();
                    window.reportFPCall({
                        category,
                        api,
                        args: args ? JSON.stringify(args) : null,
                        source,
                        timestamp: Date.now(),
                        url: document.location.href,
                        pageIndex: window.currentPageIndex || 0,
                        visit: window.currentVisitNumber
                    });
                }
            };

            // Canvas fingerprinting
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function() {
                fpCollector.report('canvas', 'getContext', Array.from(arguments));
                return originalGetContext.apply(this, arguments);
            };

            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                fpCollector.report('canvas', 'toDataURL', Array.from(arguments));
                return originalToDataURL.apply(this, arguments);
            };

            // WebGL fingerprinting
            if (WebGLRenderingContext) {
                const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    fpCollector.report('webgl', 'getParameter', parameter);
                    return originalGetParameter.apply(this, parameter);
                };
            }

            // Font fingerprinting
            if (document.fonts) {
                const originalCheck = document.fonts.check;
                document.fonts.check = function() {
                    fpCollector.report('fonts', 'check', Array.from(arguments));
                    return originalCheck.apply(this, arguments);
                };
            }

            // Hardware fingerprinting
            for (const prop of ['hardwareConcurrency', 'deviceMemory', 'platform']) {
                if (Navigator.prototype.hasOwnProperty(prop)) {
                    const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, prop);
                    if (descriptor && descriptor.get) {
                        Object.defineProperty(Navigator.prototype, prop, {
                            get: function() {
                                fpCollector.report('hardware', prop);
                                return descriptor.get.call(this);
                            }
                        });
                    }
                }
            }

            // Audio fingerprinting
            if (window.AudioContext || window.webkitAudioContext) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                const originalCreateOscillator = AudioContextClass.prototype.createOscillator;
                AudioContextClass.prototype.createOscillator = function() {
                    fpCollector.report('audio', 'createOscillator');
                    return originalCreateOscillator.apply(this, arguments);
                };
            }

            // WebRTC fingerprinting
            if (window.RTCPeerConnection) {
                const originalRTCPC = window.RTCPeerConnection;
                window.RTCPeerConnection = function() {
                    fpCollector.report('webrtc', 'RTCPeerConnection', Array.from(arguments));
                    return new originalRTCPC(...arguments);
                };
            }
        """)

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
        source = call_data['source']
        url = self._normalize_url(call_data['url'])
        visit = call_data.get('visit', self.current_visit)
        
        # Make sure this visit exists in our data structure
        if visit not in self.visits_data:
            self.visits_data[visit] = {
                'page_data': defaultdict(lambda: {
                    'api_counts': Counter(),
                    'categories': Counter(),
                    'scripts': set()
                }),
                'category_counts': Counter()
            }
        
        # Get the data for this visit
        visit_data = self.visits_data[visit]
        
        # Increment API call count for this page
        visit_data['page_data'][url]['api_counts'][api] += 1
        
        # Increment category count for this page
        visit_data['page_data'][url]['categories'][category] += 1
        
        # Store script source
        visit_data['page_data'][url]['scripts'].add(source)
        
        # Update global category counts for this visit
        visit_data['category_counts'][category] += 1
        
        # Update script patterns for fingerprinting detection (global)
        if source not in self.script_patterns:
            self.script_patterns[source] = set()
        self.script_patterns[source].add(category)

    def _is_likely_fingerprinting(self, script: str) -> bool:
        """Determine if a script is likely fingerprinting based on its behavior"""
        if script not in self.script_patterns:
            return False

        patterns = self.script_patterns[script]
        
        # Check for known fingerprinting combinations
        fp_combinations = [
            {'canvas', 'fonts'},  # Canvas + Font fingerprinting
            {'webgl', 'hardware'},  # WebGL + Hardware info
            {'canvas', 'webgl', 'hardware'},  # Multiple techniques
            {'audio', 'hardware'}  # Audio + Hardware fingerprinting
        ]

        # Check if script uses any known fingerprinting combinations
        return any(combo.issubset(patterns) for combo in fp_combinations)

    def get_fingerprinting_results(self, visit_number=None):
        """Get analysis results with aggregated statistics
        If visit_number is provided, return results for that visit,
        otherwise return combined results across all visits"""
        
        if visit_number is not None and visit_number in self.visits_data:
            # Return results for a specific visit
            return self._get_results_for_visit(visit_number)
        else:
            # Return combined results
            return self._get_combined_results()
    
    def _get_results_for_visit(self, visit_number):
        """Get fingerprinting results for a specific visit"""
        # If this visit doesn't exist in our data, create an empty structure
        if visit_number not in self.visits_data:
            print(f"Warning: No fingerprinting data for visit {visit_number}, creating empty result")
            self.visits_data[visit_number] = {
                'page_data': defaultdict(lambda: {
                    'api_counts': Counter(),
                    'categories': Counter(),
                    'scripts': set()
                }),
                'category_counts': Counter()
            }
        
        visit_data = self.visits_data[visit_number]
        page_data = visit_data['page_data']
        category_counts = visit_data['category_counts']
        
        # Get detected techniques
        detected_techniques = self._get_detected_techniques(page_data, category_counts)
        
        # Create page summaries
        page_summaries = []
        for url, data in page_data.items():
            page_summaries.append({
                'url': url,
                'total_calls': sum(data['api_counts'].values()),
                'api_breakdown': dict(data['api_counts']),
                'category_breakdown': dict(data['categories'])
            })
        
        # Calculate total calls
        total_calls = sum(sum(data['api_counts'].values()) for data in page_data.values())
        
        return {
            'visit_number': visit_number,
            'fingerprinting_detected': bool(detected_techniques) or total_calls > 0,
            'techniques_detected': list(detected_techniques),
            'page_summaries': page_summaries,
            'summary': {
                'total_calls': total_calls,
                'pages_analyzed': len(page_data),
                'category_counts': dict(category_counts)
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
                'fingerprinting_detected': visit_result['fingerprinting_detected'],
                'techniques_detected': visit_result['techniques_detected'],
                'total_calls': visit_result['summary']['total_calls']
            })
            
            # Store page summaries for this visit
            visit_page_summaries[visit_number] = visit_result['page_summaries']
            
            # Update combined data
            all_techniques.update(visit_result['techniques_detected'])
            all_category_counts.update(visit_result['summary']['category_counts'])
            total_calls += visit_result['summary']['total_calls']
            pages_analyzed.update(data['url'] for data in visit_result['page_summaries'])
        
        # Create final result
        result = {
            'fingerprinting_detected': bool(all_techniques) or total_calls > 0,
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
        for visit_number, page_summaries in visit_page_summaries.items():
            result['visit_page_data'][str(visit_number)] = page_summaries
        
        # Keep the overall page_summaries for backward compatibility
        result['page_summaries'] = []
        for summaries in visit_page_summaries.values():
            result['page_summaries'].extend(summaries)
        
        return result
    
    def _get_detected_techniques(self, page_data, category_counts):
        """Helper method to get detected techniques from page data and category counts"""
        detected_techniques = set()
        
        # Check page data first
        for data in page_data.values():
            category_breakdown = data['categories']
            if category_breakdown.get('canvas', 0) > 0:
                detected_techniques.add('canvas')
            if category_breakdown.get('webgl', 0) > 0:
                detected_techniques.add('webgl')
            if category_breakdown.get('hardware', 0) > 0:
                detected_techniques.add('hardware')
            if category_breakdown.get('audio', 0) > 0:
                detected_techniques.add('audio')
            if category_breakdown.get('fonts', 0) > 0:
                detected_techniques.add('fonts')
        
        # Check category counts as fallback
        if category_counts.get('canvas', 0) > 0:
            detected_techniques.add('canvas')
        if category_counts.get('webgl', 0) > 0:
            detected_techniques.add('webgl')  
        if category_counts.get('hardware', 0) > 0:
            detected_techniques.add('hardware')
        if category_counts.get('audio', 0) > 0:
            detected_techniques.add('audio')
        if category_counts.get('fonts', 0) > 0:
            detected_techniques.add('fonts')
        
        # Check for API usage as last fallback
        if not detected_techniques:
            for url, data in page_data.items():
                api_breakdown = data.get('api_counts', {})
                for api, count in api_breakdown.items():
                    if api in {'getContext', 'toDataURL'}:
                        detected_techniques.add('canvas')
                    elif api == 'getParameter':
                        detected_techniques.add('webgl')
                    elif api in {'hardwareConcurrency', 'deviceMemory', 'platform'}:
                        detected_techniques.add('hardware')
        
        return detected_techniques

    def get_fingerprinting_data(self):
        """Get comprehensive fingerprinting results"""
        return {
            'summary': self._get_combined_results(),
            'visits': {
                visit: self._get_results_for_visit(visit) 
                for visit in self.visits_data.keys()
            }
        }