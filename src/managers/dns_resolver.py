import os
import dns.resolver
import pickle
import time
import atexit
from cachetools import TTLCache
from tqdm import tqdm

class DNSResolver:
    """
    Class for resolving and caching DNS lookups, including following CNAME chains.
    
    Maintains two types of caches:
    1. A record cache: Domain → IP address mappings (1-hour TTL)
    2. CNAME chain cache: Domain → list of CNAME redirects (24-hour TTL)
    """
    
    def __init__(self, a_record_cache_file='data/cache/a_record_cache.pickle', 
                 cname_cache_file='data/cache/cname_chain_cache.pickle',
                 verbose=False):
        # A record cache for IP addresses (with 1-hour TTL)
        self.a_record_cache = TTLCache(maxsize=10000, ttl=3600)
        self.a_record_cache_file = a_record_cache_file
        
        # CNAME chain cache (with 24-hour TTL since CNAMEs change less frequently)
        self.cname_chain_cache = TTLCache(maxsize=10000, ttl=86400)  # 24 hours
        self.cname_cache_file = cname_cache_file
        self.verbose = verbose
        
        # Load both caches at initialization
        self._load_a_record_cache()
        self._load_cname_chain_cache()
        
        # Register cleanup on exit
        atexit.register(self.save_caches)
        
        self.a_record_lookup_count = 0
        self.cname_cache_additions = 0  # Counter for CNAME cache additions
    
    def _load_a_record_cache(self):
        """Load A record cache from file if it exists (private method)"""
        try:
            if os.path.exists(self.a_record_cache_file):
                with open(self.a_record_cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    # If loading from a dict (not TTLCache), we need to add items individually
                    loaded_count = 0
                    for key, value in cached_data.items():
                        self.a_record_cache[key] = value
                        loaded_count += 1
                    if self.verbose:
                        tqdm.write(f"Loaded {loaded_count} A record entries from cache")
        except Exception as e:
            if self.verbose:
                tqdm.write(f"Error loading A record cache: {e}")
    
    def _load_cname_chain_cache(self):
        """Load CNAME chain cache from file if it exists (private method)"""
        try:
            if os.path.exists(self.cname_cache_file):
                with open(self.cname_cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    # If loading from a dict (not TTLCache), we need to add items individually
                    loaded_count = 0
                    for key, value in cached_data.items():
                        self.cname_chain_cache[key] = value
                        loaded_count += 1
                    if self.verbose:
                        tqdm.write(f"Loaded {loaded_count} CNAME chains from cache")
        except Exception as e:
            if self.verbose:
                tqdm.write(f"Error loading CNAME chain cache: {e}")
    
    def _resolve_cname(self, domain):
        """Get the CNAME for a domain if it exists (private method)."""
        try:
            answers = dns.resolver.resolve(domain, 'CNAME')
            result = str(answers[0].target).rstrip('.')
            return result
        except dns.resolver.NoAnswer:
            return None
        except dns.resolver.NXDOMAIN:
            return None
        except Exception as e:
            tqdm.write(f"CNAME lookup error for {domain}: {str(e)}")
            return None
            
    def get_cname_chain(self, domain, lookup_ips=False):
        """
        Follow and return the complete CNAME chain until we hit an A record.
        
        Args:
            domain: The domain to resolve
            lookup_ips: Whether to also lookup and cache IPs (defaults to False)
                
        Returns:
            tuple: A tuple of CNAMEs in the resolution chain
        """
        # Normalize domain to ensure consistent caching
        domain = domain.lower().strip()
        cache_key = domain
        
        # Check if in cache
        if cache_key in self.cname_chain_cache:
            chain = self.cname_chain_cache[cache_key]
            # Only lookup IPs if specifically requested
            if lookup_ips and chain:
                final_domain = chain[-1]
                self.get_ip_addresses(final_domain)
            return chain
        
        # Not in cache, perform DNS lookups
        if self.verbose:
            tqdm.write(f"CNAME chain cache miss for: {domain}, resolving chain...")
        chain = []
        current = domain
        seen = set()  # Prevent infinite loops
        
        while True:
            cname = self._resolve_cname(current)
            if not cname or cname in seen:
                break
            chain.append(cname)
            seen.add(cname)
            current = cname
        
        # Store in cache
        result = tuple(chain)  # Convert to tuple for immutability
        self.cname_chain_cache[cache_key] = result
        
        # Increment the counter and save if needed
        self.cname_cache_additions += 1
        if self.cname_cache_additions >= 100:
            self._save_cname_chain_cache()
            self.cname_cache_additions = 0  # Reset counter
            if self.verbose:
                tqdm.write(f"CNAME chain cache automatically saved after 100 additions")
        
        # Only lookup IPs if specifically requested
        if lookup_ips:
            if chain:
                final_domain = chain[-1]
                self.get_ip_addresses(final_domain)
            else:
                self.get_ip_addresses(domain)
        
        return result
    
    def get_ip_addresses(self, domain):
        """
        Get IP addresses for a domain using A record lookup with caching.
        
        Args:
            domain: The domain to resolve
            
        Returns:
            set: A set of IP addresses as strings
        """
        # Normalize domain
        domain = domain.lower().strip()
        
        # Check cache first
        if domain in self.a_record_cache:
            return self.a_record_cache[domain]
        
        # Not in cache, do actual DNS lookup
        try:
            if self.verbose:
                tqdm.write(f"A record cache miss for {domain}, performing DNS lookup...")
            self.a_record_lookup_count += 1
            answers = dns.resolver.resolve(domain, 'A')
            
            ip_set = {str(rdata) for rdata in answers}
            
            # Store in cache
            self.a_record_cache[domain] = ip_set
            
            return ip_set
        except dns.resolver.NoAnswer:
            self.a_record_cache[domain] = set()
            return set()
        except dns.resolver.NXDOMAIN:
            self.a_record_cache[domain] = set()
            return set()
        except Exception as e:
            if self.verbose:
                tqdm.write(f"A record lookup error for {domain}: {str(e)}")
            # Cache empty result too to avoid repeated lookups
            self.a_record_cache[domain] = set()
            return set()

    def _save_a_record_cache(self):
        """Save A record cache to file (private method)"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.a_record_cache_file), exist_ok=True)
            
            # Convert TTLCache to a regular dict for serialization
            cache_dict = dict(self.a_record_cache.items())
            
            with open(self.a_record_cache_file, 'wb') as f:
                pickle.dump(cache_dict, f)
            
            if self.verbose:
                tqdm.write(f"Saved {len(self.a_record_cache)} A record entries to cache")
        except Exception as e:
            if self.verbose:
                tqdm.write(f"Error saving A record cache: {e}")

    def _save_cname_chain_cache(self):
        """Save CNAME chain cache to file (private method)"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cname_cache_file), exist_ok=True)
            
            # Convert TTLCache to a regular dict for serialization
            cache_dict = dict(self.cname_chain_cache.items())
            
            with open(self.cname_cache_file, 'wb') as f:
                pickle.dump(cache_dict, f)
            
            if self.verbose:
                tqdm.write(f"Saved {len(self.cname_chain_cache)} CNAME chains to cache")
        except Exception as e:
            if self.verbose:
                tqdm.write(f"Error saving CNAME chain cache: {e}")

    def save_caches(self):
        """Save all caches to disk (public method that can be called manually)"""
        self._save_a_record_cache()
        self._save_cname_chain_cache()
        if self.verbose:
            tqdm.write(f"DNS resolver: saved all caches, performed {self.a_record_lookup_count} A record lookups this session")