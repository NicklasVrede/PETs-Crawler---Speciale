import json
from datetime import datetime
from pathlib import Path

class StorageMonitor:
    """Simple monitor for web storage usage"""
    
    def __init__(self, verbose=False):
        """Initialize storage monitor"""
        self.storage_items = {}  # Storage data by visit
        self.api_count = {}  # API count by visit
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
            api_count = await page.evaluate("""() => {
                // Return the API usage counts
                if (window._storageMonitor) {
                    return {
                        localStorage: {
                            getItem_count: window._storageMonitor.localStorage.getItem,
                            setItem_count: window._storageMonitor.localStorage.setItem,
                            removeItem_count: window._storageMonitor.localStorage.removeItem,
                            clear_count: window._storageMonitor.localStorage.clear
                        },
                        sessionStorage: {
                            getItem_count: window._storageMonitor.sessionStorage.getItem,
                            setItem_count: window._storageMonitor.sessionStorage.setItem,
                            removeItem_count: window._storageMonitor.sessionStorage.removeItem,
                            clear_count: window._storageMonitor.sessionStorage.clear
                        }
                    };
                }
                return null;
            }""")
            
            # Store API count for this visit
            if api_count:
                self.api_count[visit_number] = api_count
            
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
            
            metrics = await page.evaluate("""() => {
                // Return the API usage counts with _count suffix
                if (window._storageMonitor) {
                    return {
                        localStorage: {
                            getItem_count: window._storageMonitor.localStorage.getItem,
                            setItem_count: window._storageMonitor.localStorage.setItem,
                            removeItem_count: window._storageMonitor.localStorage.removeItem,
                            clear_count: window._storageMonitor.localStorage.clear
                        },
                        sessionStorage: {
                            getItem_count: window._storageMonitor.sessionStorage.getItem,
                            setItem_count: window._storageMonitor.sessionStorage.setItem,
                            removeItem_count: window._storageMonitor.sessionStorage.removeItem,
                            clear_count: window._storageMonitor.sessionStorage.clear
                        }
                    };
                }
                return null;
            }""")
            
            if metrics:
                self.api_count[visit_number] = metrics
            
            return metrics
        except Exception as e:
            if self.verbose:
                print(f"[StorageMonitor] Error collecting API metrics: {e}")
            return None
    
    def get_results(self):
        """Get results of storage monitoring"""
        # Merge storage and API count data
        results = {}
        
        for visit_number, storage_data in self.storage_items.items():
            results[visit_number] = {
                'local_storage': storage_data['local_storage'],
                'session_storage': storage_data['session_storage'],
                'url': storage_data['url'],
                'local_storage_count': len(storage_data['local_storage']),
                'session_storage_count': len(storage_data['session_storage'])
            }
            
            # Add API count data if available
            if visit_number in self.api_count:
                results[visit_number]['api_count'] = self.api_count[visit_number]
        
        return results