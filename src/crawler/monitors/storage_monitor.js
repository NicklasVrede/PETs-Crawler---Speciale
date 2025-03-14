(function() {
    // Create counter object if it doesn't exist
    if (!window._storageMonitor) {
        window._storageMonitor = {
            localStorage: { getItem: 0, setItem: 0, removeItem: 0, clear: 0 },
            sessionStorage: { getItem: 0, setItem: 0, removeItem: 0, clear: 0 },
            initialized: new Date().toISOString()
        };
    }
    
    // Skip if already instrumented
    if (window._storageMonitorInstalled) return;
    
    // Instrument localStorage
    if (window.localStorage) {
        const origLocalGet = localStorage.getItem;
        localStorage.getItem = function(key) {
            window._storageMonitor.localStorage.getItem++;
            return origLocalGet.apply(this, arguments);
        };
        
        const origLocalSet = localStorage.setItem;
        localStorage.setItem = function(key, value) {
            window._storageMonitor.localStorage.setItem++;
            return origLocalSet.apply(this, arguments);
        };
        
        const origLocalRemove = localStorage.removeItem;
        localStorage.removeItem = function(key) {
            window._storageMonitor.localStorage.removeItem++;
            return origLocalRemove.apply(this, arguments);
        };
        
        const origLocalClear = localStorage.clear;
        localStorage.clear = function() {
            window._storageMonitor.localStorage.clear++;
            return origLocalClear.apply(this, arguments);
        };
    }
    
    // Instrument sessionStorage
    if (window.sessionStorage) {
        const origSessionGet = sessionStorage.getItem;
        sessionStorage.getItem = function(key) {
            window._storageMonitor.sessionStorage.getItem++;
            return origSessionGet.apply(this, arguments);
        };
        
        const origSessionSet = sessionStorage.setItem;
        sessionStorage.setItem = function(key, value) {
            window._storageMonitor.sessionStorage.setItem++;
            return origSessionSet.apply(this, arguments);
        };
        
        const origSessionRemove = sessionStorage.removeItem;
        sessionStorage.removeItem = function(key) {
            window._storageMonitor.sessionStorage.removeItem++;
            return origSessionRemove.apply(this, arguments);
        };
        
        const origSessionClear = sessionStorage.clear;
        sessionStorage.clear = function() {
            window._storageMonitor.sessionStorage.clear++;
            return origSessionClear.apply(this, arguments);
        };
    }
    
    // Mark as installed
    window._storageMonitorInstalled = true;
})(); 