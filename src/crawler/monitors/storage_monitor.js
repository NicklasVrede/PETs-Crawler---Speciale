(function() {
    // Create counter object if it doesn't exist
    if (!window._storageMonitor) {
        window._storageMonitor = {
            localStorage: { getItem: 0, setItem: 0, removeItem: 0, clear: 0 },
            sessionStorage: { getItem: 0, setItem: 0, removeItem: 0, clear: 0 },
            initialized: new Date().toISOString(),
            apiCalls: []
        };
    }
    
    // Skip if already instrumented
    if (window._storageMonitorInstalled) {
        return;
    }
    
    // Helper function to record API calls
    function recordCall(type, method, key, value) {
        const callInfo = {
            timestamp: new Date().toISOString(),
            type: type,
            method: method,
            key: key
        };
        
        // Keep last 50 calls
        window._storageMonitor.apiCalls.unshift(callInfo);
        if (window._storageMonitor.apiCalls.length > 50) {
            window._storageMonitor.apiCalls.pop();
        }
    }
    
    // Instrument localStorage
    if (window.localStorage) {
        const origLocalGet = localStorage.getItem;
        localStorage.getItem = function(key) {
            window._storageMonitor.localStorage.getItem++;
            recordCall('localStorage', 'getItem', key);
            return origLocalGet.apply(this, arguments);
        };
        
        const origLocalSet = localStorage.setItem;
        localStorage.setItem = function(key, value) {
            window._storageMonitor.localStorage.setItem++;
            recordCall('localStorage', 'setItem', key, value);
            return origLocalSet.apply(this, arguments);
        };
        
        const origLocalRemove = localStorage.removeItem;
        localStorage.removeItem = function(key) {
            window._storageMonitor.localStorage.removeItem++;
            recordCall('localStorage', 'removeItem', key);
            return origLocalRemove.apply(this, arguments);
        };
        
        const origLocalClear = localStorage.clear;
        localStorage.clear = function() {
            window._storageMonitor.localStorage.clear++;
            recordCall('localStorage', 'clear');
            return origLocalClear.apply(this, arguments);
        };
    }
    
    // Instrument sessionStorage
    if (window.sessionStorage) {
        const origSessionGet = sessionStorage.getItem;
        sessionStorage.getItem = function(key) {
            window._storageMonitor.sessionStorage.getItem++;
            recordCall('sessionStorage', 'getItem', key);
            return origSessionGet.apply(this, arguments);
        };
        
        const origSessionSet = sessionStorage.setItem;
        sessionStorage.setItem = function(key, value) {
            window._storageMonitor.sessionStorage.setItem++;
            recordCall('sessionStorage', 'setItem', key, value);
            return origSessionSet.apply(this, arguments);
        };
        
        const origSessionRemove = sessionStorage.removeItem;
        sessionStorage.removeItem = function(key) {
            window._storageMonitor.sessionStorage.removeItem++;
            recordCall('sessionStorage', 'removeItem', key);
            return origSessionRemove.apply(this, arguments);
        };
        
        const origSessionClear = sessionStorage.clear;
        sessionStorage.clear = function() {
            window._storageMonitor.sessionStorage.clear++;
            recordCall('sessionStorage', 'clear');
            return origSessionClear.apply(this, arguments);
        };
    }
    
    // Mark as installed
    window._storageMonitorInstalled = true;
})(); 