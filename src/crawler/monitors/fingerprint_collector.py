from datetime import datetime
from typing import Dict, List, Set
import json

class FingerprintCollector:
    def __init__(self):
        self.fp_data = {
            'canvas': [],
            'webgl': [],
            'fonts': [],
            'hardware': [],
            'audio': [],
            'battery': [],
            'plugins': [],
            'webrtc': []
        }
        self.current_script = None
        self.current_page = None
        self.script_patterns = {}

    async def setup_monitoring(self, page):
        """Setup monitoring before page loads"""
        print("Setting up fingerprint collection...")

        # Inject our monitoring code
        await page.add_init_script("""
            window.fpCollector = {
                calls: new Set(),
                scriptSources: new Map(),
                
                // Track script sources
                getScriptSource() {
                    const error = new Error();
                    const stack = error.stack || '';
                    const match = stack.match(/at (?:https?:\/\/[^/]+)?([^:]+):/);
                    return match ? match[1] : 'unknown';
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
                        url: document.location.href
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

    async def _handle_fp_call(self, call_data):
        """Process fingerprinting API calls"""
        category = call_data['category']
        
        # Store the call
        self.fp_data[category].append({
            'api': call_data['api'],
            'args': call_data['args'],
            'source': call_data['source'],
            'timestamp': call_data['timestamp'],
            'url': call_data['url']
        })

        # Update script patterns
        script = call_data['source']
        if script not in self.script_patterns:
            self.script_patterns[script] = set()
        self.script_patterns[script].add(category)

        # Log detection
        if self._is_likely_fingerprinting(script):
            # Reduce or remove debug prints
            # print(f"Potential fingerprinting detected in {script}")
            # print(f"Uses: {', '.join(self.script_patterns[script])}")
            pass

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
        """Get analysis results"""
        return {
            'fingerprinting_detected': len([s for s in self.script_patterns if self._is_likely_fingerprinting(s)]) > 0,
            'suspicious_scripts': [
                {
                    'script': script,
                    'techniques': list(patterns)
                }
                for script, patterns in self.script_patterns.items()
                if self._is_likely_fingerprinting(script)
            ],
            'api_calls': self.fp_data
        } 