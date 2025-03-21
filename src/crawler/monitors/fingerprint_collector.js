// Fingerprint collection script
// VISIT_NUMBER placeholder will be replaced during runtime

window.currentPageIndex = 0;  // Default to 0 for homepage
window.currentVisitNumber = VISIT_NUMBER;  // Will be replaced with actual visit number

window.fpCollector = {
    calls: new Set(),

    // Report API usage to Python
    report(category, api, value) {
        // Skip duplicate calls
        const callKey = `${category}:${api}`;
        if (this.calls.has(callKey)) {
            return;
        }
        this.calls.add(callKey);
        
        
        try {
            // Get current URL
            const url = window.location.href;
            
            // Report to Python
            window.reportFPCall({
                category: category,
                api: api,
                value: value ? String(value).substring(0, 100) : "",
                url: url,
                visit: window.currentVisitNumber
            });
        } catch (e) {
            // Ignore reporting errors
            console.error("Error reporting fingerprinting call:", e);
        }
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

// Navigator property fingerprinting
for (const prop of ['hardwareConcurrency', 'deviceMemory', 'platform', 'userAgent', 'language', 'languages', 'vendor', 'doNotTrack', 'maxTouchPoints', 'cookieEnabled']) {
    if (Navigator.prototype.hasOwnProperty(prop)) {
        const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, prop);
        if (descriptor && descriptor.get) {
            Object.defineProperty(Navigator.prototype, prop, {
                get: function() {
                    fpCollector.report('navigator', prop);
                    return descriptor.get.call(this);
                }
            });
        }
    }
}

// Screen fingerprinting
for (const prop of ['width', 'height', 'availWidth', 'availHeight', 'colorDepth', 'pixelDepth', 'orientation']) {
    if (Screen.prototype.hasOwnProperty(prop)) {
        const descriptor = Object.getOwnPropertyDescriptor(Screen.prototype, prop);
        if (descriptor && descriptor.get) {
            Object.defineProperty(Screen.prototype, prop, {
                get: function() {
                    fpCollector.report('screen', prop);
                    return descriptor.get.call(this);
                }
            });
        }
    }
}

// Window dimensions and properties
for (const prop of ['devicePixelRatio', 'innerWidth', 'innerHeight', 'outerWidth', 'outerHeight']) {
    const descriptor = Object.getOwnPropertyDescriptor(Window.prototype, prop) || 
                      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(window), prop);
    if (descriptor && descriptor.get) {
        Object.defineProperty(Window.prototype, prop, {
            get: function() {
                fpCollector.report('window', prop);
                return descriptor.get.call(this);
            }
        });
    }
}

// Storage fingerprinting
for (const prop of ['localStorage', 'sessionStorage', 'indexedDB']) {
    const descriptor = Object.getOwnPropertyDescriptor(Window.prototype, prop) ||
                      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(window), prop);
    if (descriptor && descriptor.get) {
        Object.defineProperty(Window.prototype, prop, {
            get: function() {
                fpCollector.report('storage', prop);
                return descriptor.get.call(this);
            }
        });
    }
}

// WebGL advanced fingerprinting
if (WebGLRenderingContext) {
    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        fpCollector.report('webgl', 'getParameter', parameter);
        return originalGetParameter.apply(this, arguments);
    };
    
    const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
    WebGLRenderingContext.prototype.getSupportedExtensions = function() {
        fpCollector.report('webgl', 'getSupportedExtensions');
        return originalGetSupportedExtensions.apply(this, arguments);
    };
    
    const originalGetExtension = WebGLRenderingContext.prototype.getExtension;
    WebGLRenderingContext.prototype.getExtension = function(name) {
        fpCollector.report('webgl', 'getExtension', name);
        return originalGetExtension.apply(this, arguments);
    };
}

// Date/timezone fingerprinting
const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
Date.prototype.getTimezoneOffset = function() {
    fpCollector.report('date', 'getTimezoneOffset');
    return originalGetTimezoneOffset.apply(this, arguments);
};

// Media capabilities fingerprinting
if (HTMLMediaElement) {
    const originalCanPlayType = HTMLMediaElement.prototype.canPlayType;
    HTMLMediaElement.prototype.canPlayType = function() {
        fpCollector.report('media', 'canPlayType', Array.from(arguments));
        return originalCanPlayType.apply(this, arguments);
    };
}

// Device orientation/motion detection
window.addEventListener('deviceorientation', function(event) {
    if (event.alpha !== null || event.beta !== null || event.gamma !== null) {
        fpCollector.report('sensor', 'deviceorientation');
    }
}, { once: true });

window.addEventListener('devicemotion', function() {
    fpCollector.report('sensor', 'devicemotion');
}, { once: true });

// Battery API
if (navigator.getBattery) {
    const originalGetBattery = navigator.getBattery;
    navigator.getBattery = function() {
        fpCollector.report('hardware', 'getBattery');
        return originalGetBattery.apply(this, arguments);
    };
}

// Web Speech API
if (window.speechSynthesis) {
    const originalGetVoices = speechSynthesis.getVoices;
    speechSynthesis.getVoices = function() {
        fpCollector.report('speech', 'getVoices');
        return originalGetVoices.apply(this, arguments);
    };
}

// Performance API
if (window.performance) {
    // Memory information
    if (performance.memory) {
        const memoryDescriptor = Object.getOwnPropertyDescriptor(Performance.prototype, 'memory') ||
                                Object.getOwnPropertyDescriptor(performance, 'memory');
        if (memoryDescriptor && memoryDescriptor.get) {
            Object.defineProperty(Performance.prototype, 'memory', {
                get: function() {
                    fpCollector.report('performance', 'memory');
                    return memoryDescriptor.get.call(this);
                }
            });
        }
    }
    
    // Timing information
    if (performance.timing) {
        const timingDescriptor = Object.getOwnPropertyDescriptor(Performance.prototype, 'timing') ||
                               Object.getOwnPropertyDescriptor(performance, 'timing');
        if (timingDescriptor && timingDescriptor.get) {
            Object.defineProperty(Performance.prototype, 'timing', {
                get: function() {
                    fpCollector.report('performance', 'timing');
                    return timingDescriptor.get.call(this);
                }
            });
        }
    }
}

// Document cookies
const cookieDescriptor = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
if (cookieDescriptor) {
    // Cookie getter
    if (cookieDescriptor.get) {
        Object.defineProperty(Document.prototype, 'cookie', {
            get: function() {
                fpCollector.report('storage', 'cookie.get');
                return cookieDescriptor.get.call(this);
            },
            set: cookieDescriptor.set
        });
    }
    
    // Cookie setter
    if (cookieDescriptor.set) {
        Object.defineProperty(Document.prototype, 'cookie', {
            get: cookieDescriptor.get,
            set: function(val) {
                fpCollector.report('storage', 'cookie.set', val);
                return cookieDescriptor.set.call(this, val);
            }
        });
    }
}

// WebGL2 context monitoring
if (window.WebGL2RenderingContext) {
    // Monitor getContext for WebGL2
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(contextType) {
        if (contextType === 'webgl2') {
            fpCollector.report('webgl2', 'getContext');
        }
        return originalGetContext.apply(this, arguments);
    };
    
    // Monitor WebGL2 methods
    if (WebGL2RenderingContext.prototype) {
        const webgl2Methods = [
            'getParameter', 
            'getSupportedExtensions',
            'getExtension',
            'getShaderPrecisionFormat',
            'getContextAttributes'
        ];
        
        for (const method of webgl2Methods) {
            if (WebGL2RenderingContext.prototype[method]) {
                const original = WebGL2RenderingContext.prototype[method];
                WebGL2RenderingContext.prototype[method] = function() {
                    fpCollector.report('webgl2', method, Array.from(arguments));
                    return original.apply(this, arguments);
                };
            }
        }
    }
}

// Media Devices enumeration
if (navigator.mediaDevices) {
    if (navigator.mediaDevices.enumerateDevices) {
        const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
        navigator.mediaDevices.enumerateDevices = function() {
            fpCollector.report('media', 'enumerateDevices');
            return originalEnumerateDevices.apply(this, arguments);
        };
    }
}

// Intl API for locale detection
if (window.Intl && Intl.DateTimeFormat) {
    const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {
        fpCollector.report('intl', 'resolvedOptions');
        return originalResolvedOptions.apply(this, arguments);
    };
}

// Match Media for detecting color scheme, reduced motion, etc.
if (window.matchMedia) {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = function(query) {
        fpCollector.report('media', 'matchMedia', query);
        return originalMatchMedia.apply(this, arguments);
    };
}

// More advanced canvas fingerprinting methods
if (CanvasRenderingContext2D) {
    const canvasMethods = ['measureText', 'getImageData', 'isPointInPath'];
    
    for (const method of canvasMethods) {
        if (CanvasRenderingContext2D.prototype[method]) {
            const original = CanvasRenderingContext2D.prototype[method];
            CanvasRenderingContext2D.prototype[method] = function() {
                fpCollector.report('canvas', method, Array.from(arguments));
                return original.apply(this, arguments);
            };
        }
    }
}

// DOM layout detection
if (Element.prototype.getClientRects) {
    const originalGetClientRects = Element.prototype.getClientRects;
    Element.prototype.getClientRects = function() {
        fpCollector.report('dom', 'getClientRects');
        return originalGetClientRects.apply(this, arguments);
    };
}

// URL API for blob URL creation
if (URL && URL.createObjectURL) {
    const originalCreateObjectURL = URL.createObjectURL;
    URL.createObjectURL = function() {
        fpCollector.report('storage', 'createObjectURL');
        return originalCreateObjectURL.apply(this, arguments);
    };
}

// Navigator additional properties
for (const prop of ['connection', 'keyboard', 'permissions', 'presentation', 'storage', 'webkitPersistentStorage', 'webkitTemporaryStorage']) {
    if (Navigator.prototype.hasOwnProperty(prop) || prop in navigator) {
        const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, prop) || 
                          Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator), prop);
        if (descriptor && descriptor.get) {
            Object.defineProperty(Navigator.prototype, prop, {
                get: function() {
                    fpCollector.report('navigator', prop);
                    return descriptor.get.call(this);
                }
            });
        }
    }
}

// Notification permission
if (window.Notification) {
    const permissionDescriptor = Object.getOwnPropertyDescriptor(Notification, 'permission');
    if (permissionDescriptor && permissionDescriptor.get) {
        Object.defineProperty(Notification, 'permission', {
            get: function() {
                fpCollector.report('permission', 'notification');
                return permissionDescriptor.get.call(this);
            }
        });
    }
}

// Advanced audio fingerprinting
if (window.AudioContext || window.webkitAudioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    
    // More audio methods
    const audioMethods = ['createAnalyser', 'createDynamicsCompressor', 'getOutputTimestamp'];
    
    for (const method of audioMethods) {
        if (AudioContextClass.prototype[method]) {
            const original = AudioContextClass.prototype[method];
            AudioContextClass.prototype[method] = function() {
                fpCollector.report('audio', method);
                return original.apply(this, arguments);
            };
        }
    }
    
    // Monitor AudioBuffer methods
    if (window.AudioBuffer) {
        const originalGetChannelData = AudioBuffer.prototype.getChannelData;
        if (originalGetChannelData) {
            AudioBuffer.prototype.getChannelData = function() {
                fpCollector.report('audio', 'getChannelData');
                return originalGetChannelData.apply(this, arguments);
            };
        }
    }
} 