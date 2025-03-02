import sys
import os
from urllib.parse import urlparse

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.identify_sources import (
    get_base_domain,
    are_domains_related,
    get_cname_chain,
    analyze_cname_chain
)
from src.analyzers.check_filters import DomainFilterAnalyzer
from src.utils.public_suffix_updater import update_public_suffix_list

def test_cname_tracking():
    """Test CNAME-based tracking detection with known cases."""
    print("\nTesting CNAME-based tracking detection:")
    print("-" * 80)
    
    test_cases = [
        # (main_site, test_url, description)
        ("Amazon.co.uk", "https://aan.amazon.co.uk", "Suspicious subdomain"),
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
                is_tracking, evidence, categorization = analyze_cname_chain(
                    domain_analyzer,
                    parsed_url,
                    f"{main_base}.{main_suffix}",
                    cname_chain,
                    public_suffixes,
                    verbose=True
                )
                if is_tracking:
                    print("\nCNAME chain classified as tracking due to:")
                    for finding in evidence:
                        print(f"- {finding}")
                    
                    print("\nDetailed categorization:")
                    for domain, info in categorization.items():
                        print(f"\n{domain}:")
                        print(f"  Categories: {', '.join(info['categories'])}")
                        print(f"  Organizations: {', '.join(info['organizations'])}")
            else:
                print("\nNo CNAME records found")
        
        print("-" * 80)

if __name__ == "__main__":
    test_cname_tracking() 