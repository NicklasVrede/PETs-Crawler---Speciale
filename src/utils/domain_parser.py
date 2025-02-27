from urllib.parse import urlparse
from .public_suffix_updater import update_public_suffix_list

def get_base_domain(url, public_suffixes):
    """Get the base domain without subdomain or public suffix.
    
    Args:
        url (str): URL or domain name
        public_suffixes (set): Set of public suffixes from PSL
        
    Returns:
        tuple: (base_domain, public_suffix)
        Example: 
            analytics.example.co.uk -> ("example", "co.uk")
            metrics.example.dk -> ("example", "dk")
    """
    # Handle full URLs
    domain = urlparse(url).netloc if '//' in url else url
    domain = domain.lower()  # Normalize to lowercase
    
    # Split domain into parts
    parts = domain.split('.')
    
    # Find the longest matching suffix
    for i in range(len(parts)):
        potential_suffix = '.'.join(parts[i:])
        if potential_suffix in public_suffixes:
            # Found the public suffix
            if i > 0:  # Make sure we have a domain part
                return parts[i-1], potential_suffix
            return None, potential_suffix
    
    # If no public suffix found, assume last part is suffix
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, parts[0] if parts else None

def are_domains_related(domain1, domain2, public_suffixes):
    """Check if two domains are related (same base domain, different public suffixes).
    
    Args:
        domain1 (str): First domain
        domain2 (str): Second domain
        public_suffixes (set): Set of public suffixes from PSL
        
    Returns:
        bool: True if domains share the same base domain
    """
    base1, _ = get_base_domain(domain1, public_suffixes)
    base2, _ = get_base_domain(domain2, public_suffixes)
    return base1 and base2 and base1 == base2

if __name__ == "__main__":
    # Test the domain parser
    suffixes = update_public_suffix_list()
    
    test_cases = [
        # Same domain, different suffixes
        ("example.com", "example.co.uk"),
        ("example.dk", "example.com"),
        ("amazon.de", "amazon.dk"),
        ("facebook.dk", "facebook.com"),
        
        # Subdomains
        ("analytics.example.com", "metrics.example.co.uk"),
        
        # Different domains
        ("google.com", "example.com"),
        
        # Special cases
        ("something.blogspot.com", "another.blogspot.com"),
        ("test.github.io", "example.github.io")
    ]
    
    print("\nTesting domain relationships:")
    print("-" * 60)
    
    for domain1, domain2 in test_cases:
        base1, suffix1 = get_base_domain(domain1, suffixes)
        base2, suffix2 = get_base_domain(domain2, suffixes)
        related = are_domains_related(domain1, domain2, suffixes)
        
        print(f"\nComparing: {domain1} vs {domain2}")
        print(f"  Domain 1: base='{base1}', suffix='{suffix1}'")
        print(f"  Domain 2: base='{base2}', suffix='{suffix2}'")
        print(f"  Related? {related}") 