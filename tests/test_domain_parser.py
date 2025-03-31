import unittest
import sys
from urllib.parse import urlparse
sys.path.append('.')
from src.utils.domain_parser import get_base_domain, are_domains_related
from src.utils.public_suffix_updater import update_public_suffix_list

class TestDomainRelationship(unittest.TestCase):
    
    def setUp(self):
        # Make sure we have the public suffix list
        self.public_suffixes = update_public_suffix_list()
    
    def test_first_party_relationships(self):
        """Test that first-party domain relationships are correctly identified"""
        # List of (main_domain, subdomain, expected_result) tuples
        test_cases = [
            # Basic cases
            ("amazon.co.uk", "completion.amazon.co.uk", True),
            ("amazon.co.uk", "static.amazon.co.uk", True),
            ("amazon.co.uk", "www.amazon.co.uk", True),
            ("amazon.co.uk", "images-eu.amazon.co.uk", True),
            
            # Test with different TLDs - these should be considered related
            ("amazon.co.uk", "amazon.com", True),
            ("amazon.co.uk", "amazon.de", True),
            
            # Test with different base domains
            ("amazon.co.uk", "amazonprime.co.uk", False),
            ("amazon.co.uk", "amazonaws.com", False),
            
            # Test with URLs instead of just domains
            ("https://amazon.co.uk/", "https://completion.amazon.co.uk/search/", True),
            ("https://amazon.co.uk/shop", "http://images.amazon.co.uk/images/test.jpg", True),
            ("https://amazon.co.uk/shop", "https://amazon.com/search", True),
            
            # Test with different formats
            ("AMAZON.co.uk", "completion.amazon.CO.UK", True),
            ("AMAZON.co.uk", "amazon.com", True),
            
            # Edge cases
            ("amazon.co.uk", "something.else.co.uk", False),
            ("amazon.co.uk", "amazonco.uk", False),
            ("amazon.co.uk", "famazon.co.uk", False),
            ("amazon.co.uk", "amazon.co.uk.malicious.com", False)
        ]
        
        for main_domain, test_domain, expected in test_cases:
            # Parse domains if they're full URLs
            if '://' in main_domain:
                main_domain = urlparse(main_domain).netloc
            if '://' in test_domain:
                test_domain = urlparse(test_domain).netloc
                
            # Test the relationship
            is_related = are_domains_related(main_domain, test_domain, self.public_suffixes)
            
            self.assertEqual(
                is_related, 
                expected,
                f"Failed: '{test_domain}' relatedness to '{main_domain}' should be {expected}, got {is_related}"
            )
    
    def test_get_base_domain(self):
        """Test that base domains are correctly extracted"""
        test_cases = [
            # Basic cases
            ("completion.amazon.co.uk", "amazon", "co.uk"),
            ("amazon.co.uk", "amazon", "co.uk"),
            ("www.amazon.co.uk", "amazon", "co.uk"),
            
            # Different TLDs
            ("amazon.com", "amazon", "com"),
            ("amazon.de", "amazon", "de"),
            
            # Multi-part TLDs
            ("example.co.uk", "example", "co.uk"),
            ("example.com.au", "example", "com.au"),
            
            # Special cases
            ("api.login.yahoo.co.jp", "yahoo", "co.jp"),
            ("something.blogspot.com", "something", "blogspot.com"),  # blogspot.com is in PSL
            
            # IP addresses should return None
            ("192.168.1.1", None, None)
        ]
        
        for domain, expected_base, expected_suffix in test_cases:
            base, suffix = get_base_domain(domain, self.public_suffixes)
            
            self.assertEqual(
                (base, suffix), 
                (expected_base, expected_suffix),
                f"Failed for '{domain}': expected ({expected_base}, {expected_suffix}), got ({base}, {suffix})"
            )

if __name__ == '__main__':
    unittest.main() 