import os
import json
from collections import defaultdict
from typing import Dict, List, Any
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

def load_and_parse_consent(json_dir: str, max_domains: int = None) -> Dict[str, Dict[str, Dict[str, bool]]]:
    """
    Load cookie data and extract consent settings for each profile and domain.
    Args:
        json_dir: Directory containing the JSON files
        max_domains: Maximum number of domains to process (None for all domains)
    Returns: {domain: {profile: {category: bool}}}
    """
    domain_profile_consent = defaultdict(lambda: defaultdict(dict))
    profiles = [d for d in os.listdir(json_dir) if os.path.isdir(os.path.join(json_dir, d))]
    consent_categories = {'necessary', 'preferences', 'statistics', 'marketing'}
    domains_processed = 0

    # Get first profile's domains as our sample set
    if not profiles:
        return domain_profile_consent

    profile_path = os.path.join(json_dir, profiles[0])
    domain_files = [f for f in os.listdir(profile_path) if f.endswith('.json')]
    
    # Limit domains if max_domains is set
    if max_domains:
        domain_files = domain_files[:max_domains]
        print(f"Processing {len(domain_files)} domains...")

    # Now process these domains across all profiles
    with tqdm(total=len(profiles), desc="Processing profiles") as pbar_profiles:
        for profile in profiles:
            profile_path = os.path.join(json_dir, profile)
            
            for domain_file in tqdm(domain_files, desc=f"Processing {profile}", leave=False):
                domain = domain_file.replace('.json', '')
                file_path = os.path.join(profile_path, domain_file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Check if data has the correct structure
                    if not isinstance(data, dict) or 'cookies' not in data:
                        continue

                    # Get cookies list - could be directly a list or nested under '1'
                    cookies = data['cookies']
                    if isinstance(cookies, dict) and '1' in cookies:
                        cookies = cookies['1']
                    
                    if not isinstance(cookies, list):
                        continue

                    # Look for CookieConsent cookie
                    for cookie in cookies:
                        if not isinstance(cookie, dict):
                            continue
                            
                        if cookie.get('name') == 'CookieConsent':
                            value = cookie.get('value', '')
                            if not isinstance(value, str):
                                continue
                                
                            # Parse consent values
                            consent_dict = {}
                            try:
                                parts = value.split(',')
                                for part in parts:
                                    if ':' in part:
                                        category, value_str = part.split(':')
                                        category = category.strip().lower()
                                        if category in consent_categories:
                                            consent_dict[category] = value_str.strip().lower() == 'true'
                            except Exception:
                                continue

                            if consent_dict:
                                domain_profile_consent[domain][profile] = consent_dict
                                break

                except json.JSONDecodeError as e:
                    print(f"Error processing {file_path}: {e}")
                except Exception as e:
                    print(f"Unexpected error processing {file_path}: {e}")
            
            pbar_profiles.update(1)

    if not domain_profile_consent:
        print("No consent data found in the processed files.")
        
    return domain_profile_consent

def create_consent_matrix(domain_profile_consent: Dict[str, Dict[str, Dict[str, bool]]], pbar: tqdm = None):
    """Create and save consent matrix visualizations for each domain."""
    os.makedirs('analysis/cookies/consent_matrix', exist_ok=True)
    
    categories = ['Necessary', 'Preferences', 'Statistics', 'Marketing']
    
    for domain, profile_data in domain_profile_consent.items():
        if not profile_data:
            if pbar:
                pbar.update(1)
            continue
            
        # Create matrix data
        matrix_data = []
        for profile, consent_data in profile_data.items():
            row = [
                consent_data.get('necessary', None),
                consent_data.get('preferences', None),
                consent_data.get('statistics', None),
                consent_data.get('marketing', None)
            ]
            matrix_data.append(row)
            
        df = pd.DataFrame(matrix_data, 
                         index=profile_data.keys(),
                         columns=categories)
        
        # Create visualization
        plt.figure(figsize=(10, len(profile_data) * 0.5 + 2))
        
        # Create heatmap
        sns.heatmap(df, 
                   cmap=['#FF6B6B', '#4ECB71'],  # Red for False, Green for True
                   cbar=False,
                   annot=True,
                   fmt='',
                   annot_kws={'size': 12},
                   linewidths=1,
                   linecolor='white',
                   square=True)
        
        # Customize annotation text
        for i in range(len(df.index)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                if pd.isna(value):
                    plt.text(j + 0.5, i + 0.5, '❌', 
                           ha='center', va='center',
                           color='black')
                else:
                    plt.text(j + 0.5, i + 0.5, '✓' if value else '❌',
                           ha='center', va='center',
                           color='black')

        plt.title(f'Consent Matrix for {domain}')
        plt.ylabel('Profile')
        
        # Save the plot
        plt.tight_layout()
        plt.savefig(f'analysis/cookies/consent_matrix/{domain}_consent_matrix.png',
                   bbox_inches='tight',
                   dpi=300)
        plt.close()
        
        # Also save as CSV for reference
        df.to_csv(f'analysis/cookies/consent_matrix/{domain}_consent_matrix.csv')

        if pbar:
            pbar.update(1)

def main():
    json_dir = "data/crawler_data"
    
    print("Loading and parsing consent data...")
    # Start with 10 domains for testing
    with tqdm(desc="Overall Progress") as pbar:
        domain_profile_consent = load_and_parse_consent(json_dir, max_domains=10)
        pbar.update(1)
    
    if not domain_profile_consent:
        print("No consent data found! Please check the data directory path.")
        return
    
    print("\nCreating consent matrix visualizations...")
    total_domains = len(domain_profile_consent)
    with tqdm(total=total_domains, desc="Creating visualizations") as pbar:
        create_consent_matrix(domain_profile_consent, pbar)
    
    print("\nDone! Check the visualizations in analysis/cookies/consent_matrix/")

if __name__ == "__main__":
    main() 