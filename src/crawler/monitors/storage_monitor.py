import json
from datetime import datetime
from pathlib import Path

class StorageMonitor:
    """Simple monitor for web storage usage"""
    
    def __init__(self, verbose=False):
        """Initialize storage monitor"""
        self.storage_items = {}  # Storage data by visit
        self.api_usage = {}  # API usage by visit
        self.verbose = verbose
        self.setup_complete = False
        
        # Get path to the JavaScript file
        script_path = Path(__file__).parent / "storage_monitor.js"
        with open(script_path, 'r') as f:
            self.monitor_js = f.read()
        
        if self.verbose:
            print(f"[StorageMonitor] Initialized with verbose={verbose}")
    
    async def setup_monitoring(self, page):
        """Set up storage monitoring on the page"""
        try:
            if self.verbose:
                print("[StorageMonitor] Setting up monitoring...")
            
            # Add the script as init script to ensure it runs on every navigation
            await page.add_init_script(self.monitor_js)
            
            # Also inject it immediately if we're on a page already
            if page.url != "about:blank":
                await page.evaluate(self.monitor_js)
            
            self.setup_complete = True
            return True
        except Exception as e:
            if self.verbose:
                print(f"[StorageMonitor] Error setting up monitoring: {e}")
            return False
    
    async def capture_snapshot(self, page, visit_number=0):
        """Capture current storage state"""
        try:
            if self.verbose:
                print(f"[StorageMonitor] Capturing storage snapshot for visit {visit_number}")
            
            # Ensure monitoring is set up
            if not self.setup_complete:
                await self.setup_monitoring(page)
            
            # Force install the monitor directly on the page
            await page.evaluate(self.monitor_js)
            
            # Get localStorage
            local_storage = await page.evaluate("""() => {
                const items = [];
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    items.push({
                        key: key,
                        value: localStorage.getItem(key)
                    });
                }
                return items;
            }""")
            
            # Get sessionStorage
            session_storage = await page.evaluate("""() => {
                const items = [];
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    items.push({
                        key: key,
                        value: sessionStorage.getItem(key)
                    });
                }
                return items;
            }""")
            
            # Get API usage counters
            api_usage = await page.evaluate("""() => {
                // Return the API usage counts
                if (window._storageMonitor) {
                    return {
                        localStorage: {
                            getItem: window._storageMonitor.localStorage.getItem,
                            setItem: window._storageMonitor.localStorage.setItem,
                            removeItem: window._storageMonitor.localStorage.removeItem,
                            clear: window._storageMonitor.localStorage.clear
                        },
                        sessionStorage: {
                            getItem: window._storageMonitor.sessionStorage.getItem,
                            setItem: window._storageMonitor.sessionStorage.setItem,
                            removeItem: window._storageMonitor.sessionStorage.removeItem,
                            clear: window._storageMonitor.sessionStorage.clear
                        }
                    };
                }
                return null;
            }""")
            
            # Store API usage for this visit
            if api_usage:
                self.api_usage[visit_number] = api_usage
            
            # Store snapshot
            self.storage_items[visit_number] = {
                'local_storage': local_storage,
                'session_storage': session_storage,
                'url': page.url
            }
            
            return self.storage_items[visit_number]
        except Exception as e:
            if self.verbose:
                print(f"[StorageMonitor] Error capturing storage: {e}")
            return None
    
    async def collect_api_metrics(self, page, visit_number):
        """Collect storage API usage metrics"""
        try:
            if self.verbose:
                print(f"[StorageMonitor] Collecting API metrics for visit {visit_number}")
            
            metrics = await page.evaluate("window._storageMonitor || null")
            if metrics:
                self.api_usage[visit_number] = metrics
            
            return metrics
        except Exception as e:
            if self.verbose:
                print(f"[StorageMonitor] Error collecting API metrics: {e}")
            return None
    
    def get_results(self):
        """Get results of storage monitoring"""
        # Count items
        local_count = sum(len(v['local_storage']) for v in self.storage_items.values())
        session_count = sum(len(v['session_storage']) for v in self.storage_items.values())
        
        # Calculate API totals
        totals = {
            'localStorage_getItem': 0,
            'localStorage_setItem': 0, 
            'localStorage_removeItem': 0,
            'localStorage_clear': 0,
            'sessionStorage_getItem': 0,
            'sessionStorage_setItem': 0,
            'sessionStorage_removeItem': 0,
            'sessionStorage_clear': 0
        }
        
        # Add up API calls across all visits
        for data in self.api_usage.values():
            if 'localStorage' in data:
                totals['localStorage_getItem'] += data['localStorage'].get('getItem', 0)
                totals['localStorage_setItem'] += data['localStorage'].get('setItem', 0)
                totals['localStorage_removeItem'] += data['localStorage'].get('removeItem', 0)
                totals['localStorage_clear'] += data['localStorage'].get('clear', 0)
            
            if 'sessionStorage' in data:
                totals['sessionStorage_getItem'] += data['sessionStorage'].get('getItem', 0)
                totals['sessionStorage_setItem'] += data['sessionStorage'].get('setItem', 0)
                totals['sessionStorage_removeItem'] += data['sessionStorage'].get('removeItem', 0)
                totals['sessionStorage_clear'] += data['sessionStorage'].get('clear', 0)
        
        # Build stats dictionary
        stats = {
            'local_storage_count': local_count,
            'session_storage_count': session_count,
            **totals,
            'api_usage_by_visit': self.api_usage
        }
        
        return {
            'visits': self.storage_items,
            'stats': stats
        }