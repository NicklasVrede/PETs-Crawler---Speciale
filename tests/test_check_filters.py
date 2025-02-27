import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import dns.resolver
import dns.exception
from urllib.parse import urlparse

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzers.check_filters import DomainFilterAnalyzer

class TestDomainFilterAnalyzer(unittest.TestCase):
    def setUp(self):
        self.domain_analyzer = DomainFilterAnalyzer()
        
        # Test cases format: (url, expected_cloaking)
        self.test_urls = [
            ("matillion-cdc-dev.qatarairways.tt.omtrdc.net", True)

        ]

    def test_cname_identification(self):
        """Test identification of CNAME-based tracking"""
        print("\nCNAME Identification Test Results:")
        print("-" * 80)
        
        failures = []
        for url, expected_cloaking in self.test_urls:
            # Get domain from URL
            domain = urlparse(url).netloc if '//' in url else url
            
            # Test the domain
            is_cloaked, rule, is_direct = self.domain_analyzer.check_for_cname_cloaking(domain)
            cname = self.domain_analyzer.resolve_cname(domain)
            
            # Print detailed report for this URL
            print(f"\nDomain: {domain}")
            print(f"CNAME Resolution: {cname if cname else 'None'}")
            print(f"Is CNAME cloaked: {is_cloaked}")
            print(f"Is direct tracker: {is_direct}")
            print(f"Matching rule: {rule if rule else 'None'}")
            print(f"Expected cloaking: {expected_cloaking}")
            print(f"Test result: {'PASS' if is_cloaked == expected_cloaking else 'FAIL'}")
            print("-" * 40)
            
            # Collect failures
            if is_cloaked != expected_cloaking:
                failures.append(f"Failed for {domain}: expected {expected_cloaking}, got {is_cloaked}")
        
        # Assert all tests passed
        self.assertEqual([], failures, "\n".join(failures))

if __name__ == '__main__':
    unittest.main(verbosity=2)