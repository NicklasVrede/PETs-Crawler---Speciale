import os
import sys

# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Now import project modules
import pickle
import fnmatch
import atexit
from urllib.parse import urlparse
from src.utils.public_suffix_updater import update_public_suffix_list

class FilterManager:
    def __init__(self, filter_dir='data/filters', cache_file='data/cache/filter_cache.pkl'):
        if not os.path.exists(filter_dir):
            raise FileNotFoundError(f"Filter directory not found: {filter_dir}")
        
        self.filters = self.load_all_filters(filter_dir)
        if not self.filters:
            raise ValueError("No filter rules were loaded")
        
        # Initialize cache
        self.cache_file = cache_file
        self.cache_dir = os.path.dirname(cache_file)
        self.cache = self.load_cache()
        
        # Initialize public suffixes
        self.public_suffixes = update_public_suffix_list()
        
        # Register save_cache to run at exit
        atexit.register(self.save_cache)
    
    def load_cache(self):
        """Load domain check cache from pickle file."""
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        # Try to load existing cache, or create new one
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except (pickle.PickleError, EOFError):
                print(f"Warning: Could not load cache from {self.cache_file}, creating new cache")
                return {}
        return {}
    
    def save_cache(self):
        """Save domain check cache to pickle file."""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception:
            # Just silently fail during shutdown
            pass

    def load_filter_list(self, file_path):
        """Load and parse a filter list from a file."""
        if not os.path.exists(file_path):
            return []
            
        with open(file_path, 'r', encoding='utf-8') as f:
            rules = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('!'):
                    # Convert AdBlock Plus rules to domain patterns
                    if line.startswith('||'):
                        # Remove || prefix and ^ suffix
                        domain = line[2:]
                        if domain.endswith('^'):
                            domain = domain[:-1]
                        # Remove any additional options after $
                        domain = domain.split('$')[0]
                        rules.append(domain)
                    else:
                        rules.append(line)
            return rules

    def load_all_filters(self, filter_dir):
        """Load all filter lists from the specified directory."""
        filters = {}
        filter_files = [f for f in os.listdir(filter_dir) if f.endswith('_filter.txt')]
        
        for file_name in filter_files:
            filter_name = file_name.replace('_filter.txt', '').replace('_', ' ').title()
            file_path = os.path.join(filter_dir, file_name)
            filters[filter_name] = self.load_filter_list(file_path)
        
        return filters

    def is_domain_in_filters(self, domain):
        """Check if a domain matches any rule in the loaded filter lists."""
        # Check if domain is in cache
        if domain in self.cache:
            return self.cache[domain]
        
        parsed_domain = urlparse(domain).netloc if '//' in domain else domain
        domain_parts = parsed_domain.split('.')
        
        for filter_name, rules in self.filters.items():
            for rule in rules:
                # Direct match
                if rule == parsed_domain:
                    result = (filter_name, rule)
                    self.cache[domain] = result
                    return result
                
                # Check if any part of the domain matches the rule
                for i in range(len(domain_parts)):
                    subdomain = '.'.join(domain_parts[i:])
                    if subdomain == rule:
                        result = (filter_name, rule)
                        self.cache[domain] = result
                        return result
                    
                    # Domain suffix match (e.g., criteo.com matches gum.criteo.com)
                    if subdomain.endswith('.' + rule) or subdomain == rule:
                        result = (filter_name, rule)
                        self.cache[domain] = result
                        return result
                
                # Wildcard match
                if '*' in rule and fnmatch.fnmatch(parsed_domain, rule):
                    result = (filter_name, rule)
                    self.cache[domain] = result
                    return result
        
        # Cache negative results too
        self.cache[domain] = (None, None)
        return None, None

# Example usage
if __name__ == "__main__":
    # Create an instance of the FilterManager
    analyzer = FilterManager()
    
    # List of URLs to check
    urls_to_check = [
        'https://a.media-amazon.com'
    ]
    
    # Check each URL against filter lists
    for url in urls_to_check:
        filter_name, rule = analyzer.is_domain_in_filters(url)
        if filter_name:
            print(f"Tracker detected for URL '{url}'")
            print(f"  Filter list: {filter_name}")
            print(f"  Matching rule: {rule}")
        else:
            print(f"No tracker detected for URL '{url}'")
