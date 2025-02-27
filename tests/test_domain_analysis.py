import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import the modules
from urllib.parse import urlparse
from src.identify_sources import (
    get_base_domain,
    are_domains_related,
    get_cname_chain,
    analyze_cname_chain
)
from analyzers.check_filters import DomainFilterAnalyzer
from utils.public_suffix_updater import update_public_suffix_list

def test_domain_processing():
    """Test domain processing and CNAME chain analysis."""
    print("\nTesting domain processing:")
    print("-" * 80)
    
    test_cases = [
        # (main_site, test_url, description)
        ("https://plushbeds.com", "https://dnklry.plushbeds.com", "Suspicious subdomain"),
        # Add more test cases here
    ]
    
    # Initialize domain analyzer and get public suffixes
    domain_analyzer = DomainFilterAnalyzer()
    public_suffixes = update_public_suffix_list()
    
    for main_site, test_url, description in test_cases:
        print(f"\nTesting: {description}")
        print(f"Main site: {main_site}")
        print(f"Test URL: {test_url}")
        
        # Parse domains using PSL
        main_base, main_suffix = get_base_domain(main_site, public_suffixes)
        test_base, test_suffix = get_base_domain(test_url, public_suffixes)
        
        # Check if domains are related
        is_related = are_domains_related(main_site, test_url, public_suffixes)
        
        print("\nDomain parsing results:")
        print(f"Main site: base='{main_base}', suffix='{main_suffix}'")
        print(f"Test URL: base='{test_base}', suffix='{test_suffix}'")
        print(f"Are domains related? {is_related}")
        
        # If related, analyze CNAME chain
        if is_related:
            parsed_url = urlparse(test_url).netloc
            cname_chain = get_cname_chain(domain_analyzer, parsed_url)
            
            if cname_chain:
                analyze_cname_chain(
                    domain_analyzer,
                    parsed_url,
                    f"{main_base}.{main_suffix}",
                    cname_chain,
                    public_suffixes
                )
            else:
                print("\nNo CNAME records found")
        
        print("-" * 80)

if __name__ == "__main__":
    test_domain_processing() 