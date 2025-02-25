import os
import fnmatch
from urllib.parse import urlparse
import dns.resolver
from diskcache import Cache

class DomainFilterAnalyzer:
    def __init__(self, filter_dir='data/filters', cache_dir='data/cache'):
        if not os.path.exists(filter_dir):
            raise FileNotFoundError(f"Filter directory not found: {filter_dir}")
        self.filters = self.load_all_filters(filter_dir)
        if not self.filters:
            raise ValueError("No filter rules were loaded")
        self.cache = Cache(cache_dir)

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

    def is_subdomain_blocked(self, subdomain):
        """Check if a subdomain matches any rule in the loaded filter lists."""
        parsed_domain = urlparse(subdomain).netloc if '//' in subdomain else subdomain
        
        for filter_name, rules in self.filters.items():
            for rule in rules:
                # Direct match
                if rule == parsed_domain:
                    return filter_name, rule
                
                # Domain suffix match
                if parsed_domain.endswith('.' + rule) or parsed_domain == rule:
                    return filter_name, rule
                
                # Wildcard match
                if '*' in rule and fnmatch.fnmatch(parsed_domain, rule):
                    return filter_name, rule
        
        return None, None

    def resolve_cname(self, domain):
        """Resolve the CNAME for a given domain, using a cache to avoid repeated queries."""
        if domain in self.cache:
            return self.cache[domain]
        
        try:
            answers = dns.resolver.resolve(domain, 'CNAME')
            for rdata in answers:
                cname = str(rdata.target).rstrip('.')
                self.cache[domain] = cname
                return cname
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout, Exception):
            self.cache[domain] = None
            return None

    def check_for_cname_cloaking(self, url):
        """
        Check for CNAME cloaking by comparing original and resolved domains.
        Returns (is_cloaked, matching_rule, is_direct_tracker).
        """
        original_domain = urlparse(url).netloc if '//' in url else url
        
        # Check original domain first
        filter_name, original_rule = self.is_subdomain_blocked(original_domain)
        
        # If original domain is already blocked, it's not cloaking but direct tracking
        if original_rule:
            return False, original_rule, True
            
        # Check CNAME resolution
        cname_domain = self.resolve_cname(original_domain)
        if not cname_domain:
            return False, None, False
        
        # Check CNAME domain
        _, cname_rule = self.is_subdomain_blocked(cname_domain)
        
        # Only consider it cloaking if original wasn't blocked but CNAME is
        if cname_rule:
            return True, cname_rule, False
        
        return False, None, False

    def __del__(self):
        """Cleanup the cache when the object is destroyed."""
        self.cache.close()

# Example usage
if __name__ == "__main__":
    # Create an instance of the DomainFilterAnalyzer
    analyzer = DomainFilterAnalyzer()
    
    # List of URLs to check for CNAME cloaking and direct matches
    urls_to_check = [
        'https://shop.example.com',
        'https://ads.example.com',
        'https://secure.example.net',
        'https://smetrics.afpjobs.amazon.com',
        'https://marketing.advancedpractice.com',
        'https://aax-eu.amazon-adsystem.com'
    ]
    
    # Check each URL for CNAME cloaking and direct matches
    for url in urls_to_check:
        is_cloaked, matched_rule, is_direct_tracker = analyzer.check_for_cname_cloaking(url)
        
        if is_direct_tracker:
            print(f"Direct tracker detected for URL '{url}' (matched rule: '{matched_rule}').")
        elif is_cloaked:
            print(f"CNAME cloaking detected for URL '{url}' (matched rule: '{matched_rule}').")
        else:
            print(f"No tracking detected for URL '{url}'.")
