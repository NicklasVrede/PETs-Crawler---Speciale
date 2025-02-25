import unittest
from check_filters import DomainFilterAnalyzer

class TestDomainFilterAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = DomainFilterAnalyzer()

    def test_direct_tracker_matching(self):
        """Test that domains directly in filter lists are correctly identified"""
        test_cases = [
            # Known tracking domains from filter lists (with variations)
            ("marketing.advancedpractice.com", True),
            ("sub.marketing.advancedpractice.com", True),
            ("marketing.advanceflooring.co.nz", True),
            ("marketing.advantage.tech", True),
            ("marketing.advectas.se", True),
            # With protocols and paths
            ("https://marketing.advancedpractice.com/track", True),
            ("http://marketing.advanceflooring.co.nz/pixel", True),
            # Non-tracking domains
            ("example.com", False),
            ("google.com", False),
            ("notmarketing.advancedpractice.com", False),
        ]

        for url, expected_is_tracker in test_cases:
            _, _, is_direct_tracker = self.analyzer.check_for_cname_cloaking(url)
            self.assertEqual(
                is_direct_tracker, 
                expected_is_tracker,
                f"Failed for {url}: expected direct_tracker={expected_is_tracker}, got {is_direct_tracker}"
            )

    def test_rule_parsing(self):
        """Test that AdBlock Plus style rules are properly parsed"""
        test_cases = [
            ("||marketing.advancedpractice.com^", "marketing.advancedpractice.com"),
            ("||marketing.advanceflooring.co.nz^$3p", "marketing.advanceflooring.co.nz"),
            ("||marketing.advantage.tech^", "marketing.advantage.tech"),
        ]

        for rule, expected_domain in test_cases:
            # Directly check if the domain is in the loaded rules
            found = False
            for rules in self.analyzer.filters.values():
                if expected_domain in rules:
                    found = True
                    break
            self.assertTrue(found, f"Failed to find {expected_domain} from rule {rule}")

    def test_subdomain_matching(self):
        """Test that subdomains are properly matched against rules"""
        test_cases = [
            ("marketing.advancedpractice.com", True),
            ("sub.marketing.advancedpractice.com", True),
            ("notmarketing.advancedpractice.com", False),
            ("marketing.advanceflooring.co.nz", True),
            ("other.advanceflooring.co.nz", False),
        ]

        for domain, should_match in test_cases:
            filter_name, rule = self.analyzer.is_subdomain_blocked(domain)
            matches = bool(rule)
            self.assertEqual(
                matches,
                should_match,
                f"Failed for {domain}: expected match={should_match}, got {matches}"
            )

    def test_cname_cloaking_detection(self):
        """Test CNAME cloaking detection with known examples"""
        test_cases = [
            # Format: (url, expected_is_cloaked, expected_is_direct_tracker)
            ("https://metrics.example.com", False, False),  # Regular domain
            ("https://tracking.example.com", False, False), # Another regular domain
            # Add more test cases based on real CNAME examples
        ]

        for url, expected_is_cloaked, expected_is_direct in test_cases:
            is_cloaked, _, is_direct = self.analyzer.check_for_cname_cloaking(url)
            self.assertEqual(
                (is_cloaked, is_direct),
                (expected_is_cloaked, expected_is_direct),
                f"Failed for {url}"
            )

    def test_easyprivacy_rules(self):
        """Test specific rules from easyprivacy filter list"""
        test_cases = [
            # Direct matches from easyprivacy_filter.txt
            ("marketing.advancedpractice.com", True),
            ("marketing.advanceflooring.co.nz", True),
            ("marketing.advantage.tech", True),
            ("marketing.advectas.se", True),
            # Variations
            ("https://marketing.advancedpractice.com", True),
            ("http://marketing.advanceflooring.co.nz", True),
            # Non-matches
            ("other.advancedpractice.com", False),
            ("marketing.example.com", False),
        ]

        print("\nTesting EasyPrivacy rules:")
        for domain, expected_match in test_cases:
            filter_name, rule = self.analyzer.is_subdomain_blocked(domain)
            is_match = bool(rule)
            print(f"\nDomain: {domain}")
            print(f"Expected match: {expected_match}")
            print(f"Got match: {is_match}")
            print(f"Matching rule: {rule}")
            print(f"Filter name: {filter_name}")
            
            self.assertEqual(
                is_match,
                expected_match,
                f"Failed for {domain}: expected match={expected_match}, got match={is_match}"
            )

if __name__ == '__main__':
    unittest.main() 