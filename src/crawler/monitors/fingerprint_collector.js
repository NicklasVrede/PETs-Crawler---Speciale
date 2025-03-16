// Fingerprint collection script
// VISIT_NUMBER placeholder will be replaced during runtime

window.currentPageIndex = 0;  // Default to 0 for homepage
window.currentVisitNumber = VISIT_NUMBER;  // Will be replaced with actual visit number

window.fpCollector = {
    calls: new Set(),
    scriptSources: new Map(),
    
    // Track script sources
    getScriptSource() {
        try {
            const error = new Error();
            const stack = error.stack || '';
            // Look for full URLs in the stack trace
            const urlMatch = stack.match(/at (?:Object\.|)(?:https?:\/\/[^\s]+|[^\s:]+)/);
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