from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import json
import os

class CookieAnalyzer:
    def analyze_cookies(self, cookies: Dict, requests: List[Dict]) -> Dict:
        """Main analysis method combining all cookie analysis features"""
        analysis = {
            'persistence': self.analyze_persistence(cookies),
            'sharing': self.analyze_third_party_sharing(cookies, requests),
            'identifiers': self.analyze_potential_identifiers(cookies)
        }
        
        self._print_analysis_summary(analysis)
        return analysis

    def analyze_persistence(self, cookies: Dict) -> Dict:
        """Analyze cookie persistence between visits"""
        if not cookies or len(cookies) < 2:
            return None

        persistent_cookies = []
        visit_0_cookies = {cookie['name']: cookie for cookie in cookies['0']}
        visit_1_cookies = {cookie['name']: cookie for cookie in cookies['1']}

        for name, cookie in visit_0_cookies.items():
            if name in visit_1_cookies:
                cookie_data = self._analyze_cookie(cookie, visit_1_cookies[name])
                persistent_cookies.append(cookie_data)

        return {
            'total_cookies_visit_1': len(cookies['0']),
            'total_cookies_visit_2': len(cookies['1']),
            'persistent_cookies': persistent_cookies,
            'persistence_summary': self._generate_summary(persistent_cookies)
        }

    def analyze_third_party_sharing(self, cookies: Dict, requests: List[Dict]) -> Dict:
        """TODO: Analyze if cookies are shared with third parties"""
        # Placeholder for future implementation
        return {
            'implemented': False,
            'description': 'Will analyze cookie sharing across domains and third-party requests'
        }

    def analyze_potential_identifiers(self, cookies: Dict) -> Dict:
        """TODO: Identify cookies that might contain unique identifiers"""
        # Placeholder for future implementation
        return {
            'implemented': False,
            'description': 'Will analyze cookies for potential unique identifiers based on patterns and entropy'
        }

    def _analyze_cookie(self, cookie_v1, cookie_v2) -> Dict:
        """Analyze a single cookie across visits"""
        return {
            'name': cookie_v1['name'],
            'domain': cookie_v1['domain'],
            'path': cookie_v1['path'],
            'security': {
                'httpOnly': cookie_v1['httpOnly'],
                'secure': cookie_v1['secure'],
                'sameSite': cookie_v1['sameSite']
            },
            'changes': {
                'value_changed': cookie_v1['value'] != cookie_v2['value'],
                'expiry_changed': cookie_v1['expires'] != cookie_v2['expires']
            },
            'expiry': {
                'expires_timestamp': cookie_v1['expires'],
                'expires_in_days': round((cookie_v1['expires'] - datetime.now().timestamp()) / 86400, 1)
            }
        }

    def _generate_summary(self, persistent_cookies: List[Dict]) -> Dict:
        """Generate summary statistics about persistent cookies"""
        return {
            'total_persistent': len(persistent_cookies),
            'security_stats': {
                'secure_cookies': len([c for c in persistent_cookies if c['security']['secure']]),
                'httponly_cookies': len([c for c in persistent_cookies if c['security']['httpOnly']]),
                'samesite_strict': len([c for c in persistent_cookies if c['security']['sameSite'] == 'Strict']),
                'samesite_lax': len([c for c in persistent_cookies if c['security']['sameSite'] == 'Lax']),
                'samesite_none': len([c for c in persistent_cookies if c['security']['sameSite'] == 'None'])
            },
            'expiry_stats': {
                'short_term': len([c for c in persistent_cookies if c['expiry']['expires_in_days'] <= 7]),
                'medium_term': len([c for c in persistent_cookies if 7 < c['expiry']['expires_in_days'] <= 30]),
                'long_term': len([c for c in persistent_cookies if c['expiry']['expires_in_days'] > 30])
            }
        }

    def _print_analysis_summary(self, analysis: Dict):
        """Print a human-readable summary of the cookie analysis"""
        if persistence := analysis['persistence']:
            print("\nCookie Persistence Analysis:")
            print(f"Total cookies in first visit: {persistence['total_cookies_visit_1']}")
            print(f"Total cookies in second visit: {persistence['total_cookies_visit_2']}")
            print(f"Persistent cookies: {persistence['persistence_summary']['total_persistent']}")
            
            if persistence['persistent_cookies']:
                print("\nPersistent Cookies Details:")
                for cookie in persistence['persistent_cookies']:
                    print(f"\n{cookie['name']}:")
                    print(f"  Domain: {cookie['domain']}")
                    print(f"  Expires in: {cookie['expiry']['expires_in_days']} days")
                    print(f"  Security: {'🔒' if cookie['security']['secure'] else '🔓'} "
                          f"{'🔐' if cookie['security']['httpOnly'] else '👀'} "
                          f"SameSite={cookie['security']['sameSite']}")
                    print(f"  Value changed between visits: {'Yes' if cookie['changes']['value_changed'] else 'No'}")

def analyze_site_cookies(json_file_path: str) -> None:
    """Analyze cookies for a single site's data file"""
    print(f"\nAnalyzing cookies from {json_file_path}")
    
    # Load site data
    with open(json_file_path, 'r') as f:
        site_data = json.load(f)
    
    # Create analyzer and run analysis
    analyzer = CookieAnalyzer()
    cookie_analysis = analyzer.analyze_cookies(
        site_data['cookies'],
        site_data['network_data']['requests']
    )
    
    # Add analysis to site data
    site_data['cookie_analysis'] = cookie_analysis
    
    # Save updated data
    with open(json_file_path, 'w') as f:
        json.dump(site_data, f, indent=2)

if __name__ == "__main__":
    # Just process files in the existing directory
    data_dir = os.path.join('data', 'crawler_data', 'i_dont_care_about_cookies')
    if not os.path.exists(data_dir):
        print(f"Error: Directory not found: {data_dir}")
        exit(1)
        
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} files to analyze in {data_dir}")
    
    for json_file in json_files:
        try:
            file_path = os.path.join(data_dir, json_file)
            analyze_site_cookies(file_path)
        except Exception as e:
            print(f"Error analyzing {json_file}: {e}")