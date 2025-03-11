from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import json
from typing import Dict, Set, List
from collections import defaultdict

class StorageMonitor:
    """Monitor web storage for tracking behavior"""
    def __init__(self):
        self.storage_data = []
        
    async def capture_snapshot(self, page, visit_number):
        """Capture detailed state of web storage with visit number"""
        storage_data = await page.evaluate("""() => {
            const getStorageSize = (storage) => {
                try {
                    let size = 0;
                    for (let key in storage) {
                        if (storage.hasOwnProperty(key)) {
                            size += (String(storage[key]).length + key.length) * 2; // UTF-16
                        }
                    }
                    return size;
                } catch (e) {
                    return 0; // Return 0 if there's any error calculating size
                }
            };
            
            // Get localStorage data
            const localStorage_data = Object.entries(localStorage).map(([key, value]) => ({
                key,
                value,
                size: (String(key).length + String(value).length) * 2,
                potential_identifier: (
                    /id|uuid|visitor|user|track|analytic/i.test(key) ||
                    /^[A-Za-z0-9-_]{21,}$/.test(value) ||
                    /^[0-9]{10,13}$/.test(value)
                )
            }));
            
            // Get sessionStorage data
            const sessionStorage_data = Object.entries(sessionStorage).map(([key, value]) => ({
                key,
                value,
                size: (String(key).length + String(value).length) * 2,
                potential_identifier: (
                    /id|uuid|visitor|user|track|analytic/i.test(key) ||
                    /^[A-Za-z0-9-_]{21,}$/.test(value) ||
                    /^[0-9]{10,13}$/.test(value)
                )
            }));
            
            // Get Cache Storage data
            let cacheStorage_data = [];
            try {
                // This needs to be awaited, so we'll return a promise that resolves with all our data
                return caches.keys().then(async cacheNames => {
                    for (const cacheName of cacheNames) {
                        try {
                            const cache = await caches.open(cacheName);
                            const requests = await cache.keys();
                            const urls = requests.map(req => req.url);
                            
                            cacheStorage_data.push({
                                name: cacheName,
                                urls: urls,
                                entry_count: urls.length,
                                // Estimate size - this is rough as we don't have access to the actual size
                                size_estimate: urls.length * 5000 // Very rough estimate of ~5KB per cached item
                            });
                        } catch (e) {
                            cacheStorage_data.push({
                                name: cacheName,
                                error: e.toString()
                            });
                        }
                    }
                    
                    // Get Service Worker registrations
                    let serviceWorker_data = [];
                    try {
                        return navigator.serviceWorker.getRegistrations().then(async registrations => {
                            for (const registration of registrations) {
                                const sw = {
                                    scope: registration.scope,
                                    state: registration.active ? 'active' : 
                                           registration.installing ? 'installing' : 
                                           registration.waiting ? 'waiting' : 'unknown',
                                    scriptURL: registration.active?.scriptURL || 
                                              registration.installing?.scriptURL || 
                                              registration.waiting?.scriptURL,
                                    updateViaCache: registration.updateViaCache,
                                    // For active service workers
                                    active: registration.active ? {
                                        state: registration.active.state,
                                        scriptURL: registration.active.scriptURL
                                    } : null,
                                    // For service workers in the waiting state
                                    waiting: registration.waiting ? {
                                        state: registration.waiting.state,
                                        scriptURL: registration.waiting.scriptURL
                                    } : null,
                                    // get pushManager subscription if exists
                                    pushSubscription: false
                                };
                                
                                // Check if there's a push subscription
                                try {
                                    const subscription = await registration.pushManager.getSubscription();
                                    if (subscription) {
                                        sw.pushSubscription = true;
                                    }
                                } catch (e) {
                                    // Push subscription check failed
                                }
                                
                                serviceWorker_data.push(sw);
                            }
                            
                            return {
                                url: document.location.href,
                                timestamp: Date.now(),
                                localStorage: {
                                    entries: localStorage_data,
                                    totalSize: getStorageSize(localStorage) || 0,
                                    itemCount: localStorage.length || 0
                                },
                                sessionStorage: {
                                    entries: sessionStorage_data, 
                                    totalSize: getStorageSize(sessionStorage) || 0,
                                    itemCount: sessionStorage.length || 0
                                },
                                cacheStorage: {
                                    caches: cacheStorage_data,
                                    cache_count: cacheStorage_data.length,
                                    total_entries: cacheStorage_data.reduce((sum, cache) => sum + (cache.entry_count || 0), 0)
                                },
                                serviceWorkers: {
                                    registrations: serviceWorker_data,
                                    count: serviceWorker_data.length
                                }
                            };
                        }).catch(e => {
                            // If service worker API fails
                            return {
                                url: document.location.href,
                                timestamp: Date.now(),
                                localStorage: {
                                    entries: localStorage_data,
                                    totalSize: getStorageSize(localStorage) || 0,
                                    itemCount: localStorage.length || 0
                                },
                                sessionStorage: {
                                    entries: sessionStorage_data,
                                    totalSize: getStorageSize(sessionStorage) || 0,
                                    itemCount: sessionStorage.length || 0
                                },
                                cacheStorage: {
                                    error: e.toString(),
                                    caches: []
                                },
                                serviceWorkers: {
                                    error: e.toString(),
                                    registrations: []
                                }
                            };
                        });
                    } catch (e) {
                        // If service worker API is not available
                        return {
                            url: document.location.href,
                            timestamp: Date.now(),
                            localStorage: {
                                entries: localStorage_data,
                                totalSize: getStorageSize(localStorage) || 0,
                                itemCount: localStorage.length || 0
                            },
                            sessionStorage: {
                                entries: sessionStorage_data,
                                totalSize: getStorageSize(sessionStorage) || 0,
                                itemCount: sessionStorage.length || 0
                            },
                            cacheStorage: {
                                error: "Service Worker API not available",
                                caches: []
                            },
                            serviceWorkers: {
                                error: "Service Worker API not available",
                                registrations: []
                            }
                        };
                    }
                }).catch(e => {
                    // If caches API fails, still return the other storage data
                    return {
                        url: document.location.href,
                        timestamp: Date.now(),
                        localStorage: {
                            entries: localStorage_data,
                            totalSize: getStorageSize(localStorage) || 0,
                            itemCount: localStorage.length || 0
                        },
                        sessionStorage: {
                            entries: sessionStorage_data,
                            totalSize: getStorageSize(sessionStorage) || 0,
                            itemCount: sessionStorage.length || 0
                        },
                        cacheStorage: {
                            error: e.toString(),
                            caches: []
                        },
                        serviceWorkers: {
                            error: e.toString(),
                            registrations: []
                        }
                    };
                });
            } catch (e) {
                // If caches API is not available
                return {
                    url: document.location.href,
                    timestamp: Date.now(),
                    localStorage: {
                        entries: localStorage_data,
                        totalSize: getStorageSize(localStorage) || 0,
                        itemCount: localStorage.length || 0
                    },
                    sessionStorage: {
                        entries: sessionStorage_data,
                        totalSize: getStorageSize(sessionStorage) || 0,
                        itemCount: sessionStorage.length || 0
                    },
                    cacheStorage: {
                        error: "Cache API not available",
                        caches: []
                    },
                    serviceWorkers: {
                        error: "Service Worker API not available",
                        registrations: []
                    }
                };
            }
        }""")
        
        # Add metadata
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'url': page.url,
            'visit_number': visit_number,
            'storage': storage_data
        }
        
        self.storage_data.append(snapshot)
    
    def get_results(self):
        """Get storage data with tracking analysis"""
        tracking_summary = {
            'potential_trackers': set(),
            'storage_usage': {
                'localStorage': [],
                'sessionStorage': [],
                'cacheStorage': [],
                'serviceWorkers': []
            },
            'identifier_patterns': set(),
            'service_workers': [],  # Store all service workers
            'cached_urls': []
        }
        
        # Analyze storage data for tracking patterns
        for snapshot in self.storage_data:
            storage = snapshot['storage']
            
            # Analyze localStorage
            for entry in storage['localStorage']['entries']:
                if entry['potential_identifier']:
                    tracking_summary['potential_trackers'].add(entry['key'])
                    if len(entry['value']) > 20:  # Long values might be identifiers
                        tracking_summary['identifier_patterns'].add(
                            f"localStorage:{entry['key']}:{len(entry['value'])}"
                        )
            
            # Track storage usage over time
            tracking_summary['storage_usage']['localStorage'].append({
                'timestamp': snapshot['timestamp'],
                'url': snapshot['url'],
                'size': storage['localStorage']['totalSize'],
                'items': storage['localStorage']['itemCount']
            })
            
            # Similar analysis for sessionStorage
            # ... (similar code for sessionStorage)
            
            # Track cache storage usage 
            if 'cacheStorage' in storage:
                tracking_summary['storage_usage']['cacheStorage'].append({
                    'timestamp': snapshot['timestamp'],
                    'url': snapshot['url'],
                    'cache_count': storage['cacheStorage'].get('cache_count', 0),
                    'total_entries': storage['cacheStorage'].get('total_entries', 0)
                })
                
                # Store all cached URLs for later analysis
                all_cache_urls = []
                for cache in storage['cacheStorage'].get('caches', []):
                    cache_name = cache.get('name', 'unknown')
                    for url in cache.get('urls', []):
                        all_cache_urls.append({
                            'cache_name': cache_name,
                            'url': url,
                            'visit_number': snapshot['visit_number']
                        })
                
                # Add all cache URLs to the results
                if all_cache_urls:
                    if 'cached_urls' not in tracking_summary:
                        tracking_summary['cached_urls'] = []
                    tracking_summary['cached_urls'].extend(all_cache_urls)
                    
                    # flag obvious trackers
                    for url_data in all_cache_urls:
                        url = url_data['url']
                        if any(tracker in url.lower() for tracker in ['analytics', 'tracking', 'pixel', 'beacon', 'collect']):
                            tracking_summary['potential_trackers'].add(url)
            
            # Simply log all service workers 
            if 'serviceWorkers' in storage:
                # Add basic stats to storage usage
                tracking_summary['storage_usage']['serviceWorkers'].append({
                    'timestamp': snapshot['timestamp'],
                    'url': snapshot['url'],
                    'count': storage['serviceWorkers'].get('count', 0)
                })
                
                # Store all service workers for later analysis
                for sw in storage['serviceWorkers'].get('registrations', []):
                    if sw.get('scriptURL'):
                        sw_data = {
                            'script_url': sw.get('scriptURL'),
                            'scope': sw.get('scope'),
                            'state': sw.get('state'),
                            'has_push': sw.get('pushSubscription', False),
                            'visit_number': snapshot['visit_number'],
                            'timestamp': snapshot['timestamp']
                        }
                        tracking_summary['service_workers'].append(sw_data)
                        
                        # Flag the most obvious tracking cases
                        if sw.get('pushSubscription'):
                            tracking_summary['potential_trackers'].add(f"push_notification:{sw.get('scriptURL')}")
        
        return {
            'raw_data': self.storage_data,
            'tracking_analysis': tracking_summary
        }

class NetworkMonitor:
    def __init__(self):
        self.requests = []
        self.domains_contacted = set()
        self.storage_monitor = StorageMonitor()
        self.cookies_by_visit = {}
        # Track cookie operations per visit
        self.cookie_stats = defaultdict(lambda: {
            'created': 0,
            'deleted': 0,
            'modified': 0,
            'cookies_seen': set()  # Track unique cookies we've seen
        })

    def _count_request_types(self):
        """Count requests by type"""
        type_counts = defaultdict(int)
        for request in self.requests:
            req_type = request.get('type', 'unknown')
            type_counts[req_type] += 1
        return dict(type_counts)

    def get_cookies(self):
        """Get cookies collected during visits"""
        return self.cookies_by_visit

    def get_cookie_stats(self):
        """Get statistics about cookie operations during visits"""
        stats = {}
        for visit, data in self.cookie_stats.items():
            stats[visit] = {
                'total_unique_cookies': len(data['cookies_seen']),
                'cookies_created': data['created'],
                'cookies_deleted': data['deleted'],
                'cookies_modified': data['modified']
            }
        return stats

    def get_storage_data(self):
        """Get storage monitoring data"""
        return self.storage_monitor.get_results()

    def get_network_data(self):
        """Get network request data"""
        return {
            'requests': self.requests,
            'domains_contacted': list(self.domains_contacted)
        }

    def get_results(self):
        """Get comprehensive monitoring results"""
        return {
            'network_data': self.get_network_data(),
            'statistics': self.get_statistics()
        }

    async def setup_monitoring(self, page, visit_number=0):
        """Setup network monitoring"""
        print(f"Starting network monitor for visit {visit_number}")
        
        # Capture all browser cookies at the end of page load
        async def capture_cookies():
            current_cookies = await page.context.cookies()
            
            if visit_number not in self.cookies_by_visit:
                # First page load in this visit
                self.cookies_by_visit[visit_number] = current_cookies
                self.cookie_stats[visit_number]['created'] = len(current_cookies)
                self.cookie_stats[visit_number]['cookies_seen'].update(c['name'] for c in current_cookies)
            else:
                # Compare with previous state
                previous_cookies = {c['name']: c for c in self.cookies_by_visit[visit_number]}
                current_cookie_dict = {c['name']: c for c in current_cookies}
                
                # Check for new cookies
                new_cookies = set(current_cookie_dict.keys()) - set(previous_cookies.keys())
                self.cookie_stats[visit_number]['created'] += len(new_cookies)
                
                # Check for deleted cookies
                deleted_cookies = set(previous_cookies.keys()) - set(current_cookie_dict.keys())
                self.cookie_stats[visit_number]['deleted'] += len(deleted_cookies)
                
                # Check for modified cookies
                for name in set(previous_cookies.keys()) & set(current_cookie_dict.keys()):
                    if previous_cookies[name]['value'] != current_cookie_dict[name]['value']:
                        self.cookie_stats[visit_number]['modified'] += 1
                
                # Update current state
                self.cookies_by_visit[visit_number] = current_cookies
                self.cookie_stats[visit_number]['cookies_seen'].update(c['name'] for c in current_cookies)
            
        # Capture cookies after each navigation
        page.on('load', lambda: capture_cookies())
        
        async def handle_request(route, request):
            url = request.url
            domain = self._extract_domain(url)
            
            # Record detailed request info
            request_data = {
                "url": url,
                "domain": domain,
                "type": request.resource_type,  # Changed from 'unknown' to actual resource_type
                "resource_type": request.resource_type,
                "method": request.method,
                "headers": dict(request.headers),
                "timestamp": datetime.now().isoformat(),
                "visit_number": visit_number,
                "post_data": request.post_data,
                "frame_url": request.frame.url if request.frame else None,
                "is_navigation": request.is_navigation_request()
            }
            
            self.requests.append(request_data)
            self.domains_contacted.add(domain)
            
            try:
                response = await route.fetch()
                
                # Capture response data
                response_data = {
                    "status": response.status,
                    "status_text": response.status_text,
                    "headers": dict(response.headers),
                    "security_details": {
                        "protocol": response.security_details.protocol if response.security_details else None,
                        "subjectName": response.security_details.subject_name if response.security_details else None
                    }
                }
                
                # Add response data to request record
                request_data["response"] = response_data
                
                # Optionally capture response body for certain content types
                if request.resource_type in ['xhr', 'fetch'] and 'json' in response.headers.get('content-type', ''):
                    try:
                        body = await response.body()
                        request_data["response"]["body"] = body.decode('utf-8')
                    except Exception as e:
                        request_data["response"]["body_error"] = str(e)
                
                await route.fulfill(response=response)
                
            except Exception as e:
                request_data["error"] = str(e)
                try:
                    await route.continue_()
                except:
                    pass

        # Monitor ALL network requests
        await page.route("**", lambda route: handle_request(route, route.request))
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url.split('/')[2] if '://' in url else url.split('/')[0]
    
    def get_statistics(self):
        """Get comprehensive statistics"""
        return {
            'total_requests': len(self.requests),
            'request_types': self._count_request_types(),
            'cookie_operations': self.get_cookie_stats()
        }

    def finalize_visit(self, visit_number):
        """Store the final state of cookies for this visit"""
        if visit_number in self.cookies_by_visit:
            del self.cookies_by_visit[visit_number]
