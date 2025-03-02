from datetime import datetime
from typing import Dict, List, Set, Counter
from collections import defaultdict, Counter
import json
from urllib.parse import urlparse

class FingerprintCollector:
    def __init__(self):
        # Create a structure for aggregated data instead of raw calls
        self.page_data = defaultdict(lambda: {
            'api_counts': Counter(),
            'categories': Counter(),
            'scripts': set()
        })
        
        # Track total calls by category for final summary
        self.category_counts = Counter()
        self.script_patterns = {}

    async def setup_monitoring(self, page):
        """Setup monitoring before page loads"""
        print("Setting up fingerprint collection...")

        # Inject our monitoring code
        await page.add_init_script("""
            window.currentPageIndex = 0;  // Default to 0 for homepage
            
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
                        pageIndex: window.currentPageIndex || 0
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
        
        # Increment API call count for this page
        self.page_data[url]['api_counts'][api] += 1
        
        # Increment category count for this page
        self.page_data[url]['categories'][category] += 1
        
        # Store script source
        self.page_data[url]['scripts'].add(source)
        
        # Update global category counts
        self.category_counts[category] += 1
        
        # Update script patterns for fingerprinting detection
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

    def get_fingerprinting_results(self):
        """Get analysis results with aggregated statistics"""
        # Identify suspicious scripts
        suspicious_scripts = [
            {
                'script': script,
                'techniques': list(patterns)
            }
            for script, patterns in self.script_patterns.items()
            if self._is_likely_fingerprinting(script)
        ]
        
        # Get top pages by fingerprinting activity
        top_pages = sorted(
            self.page_data.items(), 
            key=lambda x: sum(x[1]['api_counts'].values()), 
            reverse=True
        )
        
        # Create page summaries
        page_summaries = []
        for url, data in top_pages:
            page_summaries.append({
                'url': url,
                'total_calls': sum(data['api_counts'].values()),
                'api_breakdown': dict(data['api_counts']),
                'category_breakdown': dict(data['categories']),
                'script_count': len(data['scripts'])
            })
        
        # Create overall summary
        total_calls = sum(sum(data['api_counts'].values()) for data in self.page_data.values())
        
        return {
            'fingerprinting_detected': len(suspicious_scripts) > 0,
            'suspicious_scripts': suspicious_scripts,
            'page_summaries': page_summaries,
            'summary': {
                'total_calls': total_calls,
                'pages_analyzed': len(self.page_data),
                'category_counts': dict(self.category_counts),
                'top_apis': dict(Counter({
                    api: count 
                    for page_data in self.page_data.values() 
                    for api, count in page_data['api_counts'].items()
                }).most_common(10))
            }
        } 