from datetime import datetime
import json
import os
import re
import time
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict
from urllib.parse import urlparse
import asyncio  # Added for asyncio.wait_for

# Path to save/load the database
STORAGE_DB_PATH = 'data/storage_db.json'

class StorageMonitor:
    """Monitor web storage items during page visits"""
    def __init__(self):
        self.storage_items = {}  # Storage items by visit number
        self.unique_storage_keys = set()  # Track all unique keys seen
        self.stats = {
            'snapshots_taken': 0,
            'items_added': 0,
            'items_modified': 0,
            'items_deleted': 0
        }
        
        # Load storage categories database if it exists
        self.categories_db = {}
        if os.path.exists(STORAGE_DB_PATH):
            try:
                with open(STORAGE_DB_PATH, 'r') as f:
                    self.categories_db = json.load(f)
                print(f"Loaded {len(self.categories_db)} storage items from categories database")
            except Exception as e:
                print(f"Error loading storage database: {str(e)}")
        
    async def capture_snapshot(self, page, visit_number):
        """Capture storage items for the current visit"""
        try:
            current_url = page.url
            domain = self._extract_domain(current_url)
            timestamp = datetime.now().isoformat()
            
            # Initialize storage data for this visit if it doesn't exist
            if visit_number not in self.storage_items:
                self.storage_items[visit_number] = {
                    'local_storage': [],
                    'session_storage': [],
                    'cache_storage': [],
                    'service_workers': [],
                    'meta': {
                        'timestamp': timestamp,
                        'url': current_url,
                        'domain': domain
                    }
                }
            
            # Use the most basic JavaScript possible to avoid syntax errors
            local_storage = await page.evaluate("""
                (function() {
                    try {
                        const items = [];
                        if (window.localStorage) {
                            for (let i = 0; i < localStorage.length; i++) {
                                const key = localStorage.key(i);
                                const value = localStorage.getItem(key);
                                const size = (key.length + value.length) * 2;
                                items.push({key, value, size});
                            }
                        }
                        return items;
                    } catch (e) {
                        console.error("LocalStorage error:", e);
                        return [];
                    }
                })();
            """)
            
            # Capture session storage in a separate call to isolate any errors
            session_storage = await page.evaluate("""
                (function() {
                    try {
                        const items = [];
                        if (window.sessionStorage) {
                            for (let i = 0; i < sessionStorage.length; i++) {
                                const key = sessionStorage.key(i);
                                const value = sessionStorage.getItem(key);
                                const size = (key.length + value.length) * 2;
                                items.push({key, value, size});
                            }
                        }
                        return items;
                    } catch (e) {
                        console.error("SessionStorage error:", e);
                        return [];
                    }
                })();
            """)
            
            # Process localStorage items
            if isinstance(local_storage, list):
                for item in local_storage:
                    if not isinstance(item, dict) or 'key' not in item:
                        continue
                        
                    # Create a unique key for this storage item
                    item_key = f"localStorage:{domain}:{item['key']}"
                    
                    # Only add if we haven't seen this exact item before
                    if item_key not in self.unique_storage_keys:
                        item['domain'] = domain
                        item['timestamp'] = timestamp
                        self.storage_items[visit_number]['local_storage'].append(item)
                        self.unique_storage_keys.add(item_key)
            
            # Process sessionStorage items
            if isinstance(session_storage, list):
                for item in session_storage:
                    if not isinstance(item, dict) or 'key' not in item:
                        continue
                        
                    # Create a unique key for this storage item
                    item_key = f"sessionStorage:{domain}:{item['key']}"
                    
                    # Only add if we haven't seen this exact item before
                    if item_key not in self.unique_storage_keys:
                        item['domain'] = domain
                        item['timestamp'] = timestamp
                        self.storage_items[visit_number]['session_storage'].append(item)
                        self.unique_storage_keys.add(item_key)
            
            # Try to capture cache storage (with JavaScript-only timeout)
            try:
                # Using a very basic approach to get cache names with timeout in JavaScript
                cache_storage = await page.evaluate("""
                    (function() {
                        return new Promise((resolve) => {
                            try {
                                if (!('caches' in window)) {
                                    return resolve([]);
                                }
                                
                                caches.keys().then(cacheNames => {
                                    const cachePromises = cacheNames.map(cacheName => {
                                        return caches.open(cacheName).then(cache => {
                                            return cache.keys().then(requests => {
                                                const urls = requests.map(req => req.url);
                                                return {
                                                    name: cacheName,
                                                    urls: urls,
                                                    entry_count: urls.length
                                                };
                                            }).catch(() => {
                                                return {
                                                    name: cacheName,
                                                    urls: [],
                                                    entry_count: 0,
                                                    error: "Failed to get cache keys"
                                                };
                                            });
                                        }).catch(() => {
                                            return {
                                                name: cacheName,
                                                error: "Failed to open cache"
                                            };
                                        });
                                    });
                                    
                                    Promise.all(cachePromises).then(caches => {
                                        resolve(caches);
                                    }).catch(() => {
                                        resolve([]);
                                    });
                                }).catch(() => {
                                    resolve([]);
                                });
                                
                                // Set a timeout to resolve anyway after 3 seconds
                                setTimeout(() => {
                                    resolve([]);
                                }, 3000);
                            } catch (e) {
                                console.error("Cache error:", e);
                                resolve([]);
                            }
                        });
                    })();
                """)
                
                # Process cache storage items
                if isinstance(cache_storage, list):
                    for cache in cache_storage:
                        if not isinstance(cache, dict) or 'name' not in cache:
                            continue
                            
                        cache['domain'] = domain
                        cache['timestamp'] = timestamp
                        self.storage_items[visit_number]['cache_storage'].append(cache)
                
            except Exception as e:
                print(f"Cache storage collection error: {str(e)}")
                # Continue anyway, this is optional data
            
            # Try to capture service workers (with JavaScript-only timeout)
            try:
                # Using a very basic approach to get service worker registrations
                service_workers = await page.evaluate("""
                    (function() {
                        return new Promise((resolve) => {
                            try {
                                if (!('serviceWorker' in navigator)) {
                                    return resolve([]);
                                }
                                
                                navigator.serviceWorker.getRegistrations().then(registrations => {
                                    const workers = registrations.map(reg => {
                                        return {
                                            scope: reg.scope,
                                            scriptURL: reg.active?.scriptURL || 
                                                      reg.installing?.scriptURL || 
                                                      reg.waiting?.scriptURL
                                        };
                                    });
                                    resolve(workers);
                                }).catch(() => {
                                    resolve([]);
                                });
                                
                                // Set a timeout to resolve anyway after 3 seconds
                                setTimeout(() => {
                                    resolve([]);
                                }, 3000);
                            } catch (e) {
                                console.error("Service Worker error:", e);
                                resolve([]);
                            }
                        });
                    })();
                """)
                
                # Process service worker items
                if isinstance(service_workers, list):
                    for worker in service_workers:
                        if not isinstance(worker, dict) or 'scope' not in worker:
                            continue
                            
                        worker['domain'] = domain
                        worker['timestamp'] = timestamp
                        self.storage_items[visit_number]['service_workers'].append(worker)
                
            except Exception as e:
                print(f"Service worker collection error: {str(e)}")
                # Continue anyway, this is optional data
            
        except Exception as e:
            print(f"Error capturing storage snapshot: {str(e)}")
            # Initialize with empty data to avoid further errors
            if visit_number not in self.storage_items:
                self.storage_items[visit_number] = {
                    'local_storage': [],
                    'session_storage': [],
                    'cache_storage': [],
                    'service_workers': [],
                    'meta': {
                        'timestamp': datetime.now().isoformat(),
                        'url': page.url,
                        'domain': self._extract_domain(page.url),
                        'error': str(e)
                    }
                }
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc
        except:
            return url.split('/')[2] if '://' in url else url.split('/')[0]
    
    def _classify_storage_item(self, key: str, value: str, domain: str) -> Dict:
        """
        Classify a storage item based on patterns and known categories
        """
        # Create a cache key including domain
        cache_key = f"{domain}:{key}"
        
        # Check if already in database
        if cache_key in self.categories_db:
            return self.categories_db[cache_key]
        
        # Initialize result
        result = {
            'category': 'unknown',
            'purpose': 'unknown',
            'confidence': 0
        }
        
        # Check for analytics trackers
        analytics_patterns = {
            'google_analytics': [r'^_ga', r'^ga\-', r'GoogleAnalytics', r'gtag', r'analytics'],
            'facebook': [r'^fb_', r'facebook', r'^_fbp', r'FB_'],
            'amplitude': [r'amplitude', r'device_id'],
            'segment': [r'segment', r'segmentio', r'analytics_session'],
            'mixpanel': [r'mixpanel', r'mp_'],
            'hotjar': [r'_hjSession', r'hotjar', r'_hj'],
            'matomo': [r'_pk_', r'matomo', r'piwik']
        }
        
        for tracker, patterns in analytics_patterns.items():
            for pattern in patterns:
                if re.search(pattern, key, re.IGNORECASE):
                    result['category'] = 'analytics'
                    result['purpose'] = f'{tracker} analytics tracking'
                    result['confidence'] = 0.8
                    break
        
        # Check for advertising patterns
        ad_patterns = {
            'doubleclick': [r'doubleclick', r'^dc_'],
            'adsense': [r'adsense', r'ad_storage'],
            'taboola': [r'taboola'],
            'adroll': [r'adroll'],
            'criteo': [r'criteo'],
            'outbrain': [r'outbrain']
        }
        
        for ad_network, patterns in ad_patterns.items():
            for pattern in patterns:
                if re.search(pattern, key, re.IGNORECASE):
                    result['category'] = 'advertising'
                    result['purpose'] = f'{ad_network} ad tracking'
                    result['confidence'] = 0.8
                    break
        
        # Check for functional patterns
        functional_patterns = {
            'preferences': [r'preferences', r'settings', r'config', r'theme', r'language', r'locale'],
            'authentication': [r'auth', r'token', r'session', r'user', r'login', r'logged_in'],
            'cart': [r'cart', r'basket', r'shopping'],
            'form_data': [r'form', r'input', r'saved']
        }
        
        for purpose, patterns in functional_patterns.items():
            for pattern in patterns:
                if re.search(pattern, key, re.IGNORECASE):
                    result['category'] = 'functional'
                    result['purpose'] = f'{purpose}'
                    result['confidence'] = 0.7
                    break
        
        # Store in database for future reference
        self.categories_db[cache_key] = result
        
        return result
    
    def get_results(self):
        """Get storage monitoring results"""
        # Count unique items by type
        local_storage_count = 0
        session_storage_count = 0
        cache_storage_count = 0
        service_worker_count = 0
        
        for visit_data in self.storage_items.values():
            local_storage_count += len(visit_data['local_storage'])
            session_storage_count += len(visit_data['session_storage'])
            cache_storage_count += len(visit_data['cache_storage'])
            service_worker_count += len(visit_data['service_workers'])
        
        storage_stats = {
            'unique_items': len(self.unique_storage_keys),
            'visits_with_storage': len(self.storage_items),
            'local_storage_count': local_storage_count,
            'session_storage_count': session_storage_count,
            'cache_storage_count': cache_storage_count,
            'service_worker_count': service_worker_count
        }
        
        # Return with visits directly as keys and stats at the same level
        return {
            'visits': self.storage_items,  # Keep visits under a 'visits' key
            'stats': storage_stats
        }