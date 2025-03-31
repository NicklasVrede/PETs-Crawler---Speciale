# Import necessary functions from identify_sources.py
from src.analyzers.source_identifier import get_tracker_categorization, FilterManager
from urllib.parse import urlparse

# Create test function
def test_domain(domain):
    print(f"Testing domain: {domain}")
    
    # 1. Check if domain is in TrackerDB
    tracker_info = get_tracker_categorization(domain)
    if tracker_info:
        print(f"Domain found in TrackerDB:")
        print(f"  Categories: {tracker_info['categories']}")
        print(f"  Organizations: {tracker_info['organizations']}")
    else:
        print("Domain NOT found in TrackerDB")
    
    # 2. Check if domain is in filter lists
    domain_analyzer = FilterManager()
    filter_name, rule = domain_analyzer.is_domain_in_filters("https://" + domain)
    if filter_name:
        print(f"Domain found in filter list: {filter_name}")
        print(f"Matching rule: {rule}")
    else:
        print("Domain NOT found in filter lists")
    
    print("\n--- Analysis Complete ---\n")

# Test the domain
test_domain("cloudfront-labs.amazonaws.com")