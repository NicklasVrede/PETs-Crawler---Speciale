import os
import json
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt

def get_successful_domains(csv_path="data/csv/final_data2.csv"):
    """Get domains that loaded successfully across all profiles."""
    print("Reading CSV data...")
    df = pd.read_csv(csv_path)
    
    # Filter for successful page loads
    df_loaded = df[df['page_status'] == 'loaded']
    
    # Get domains that loaded successfully across all profiles
    all_profiles = df_loaded['profile'].unique()
    successful_domains = set()
    
    print("Finding domains that loaded successfully across all profiles...")
    for domain in tqdm(df_loaded['domain'].unique(), desc="Checking domains"):
        if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
               for profile in all_profiles):
            successful_domains.add(domain)
    
    print(f"Found {len(successful_domains)} domains that loaded successfully across all profiles")
    return successful_domains

def analyze_cname_cloaking(profile="no_extensions", successful_domains=None):
    """Analyze CNAME cloaking in JSON files for a specific profile."""
    json_dir = os.path.join("data/crawler_data", profile)
    cloaked_domains = defaultdict(int)
    
    # Find JSON files for successful domains only
    json_files = []
    for domain in successful_domains:
        json_path = os.path.join(json_dir, f"{domain}.json")
        if os.path.exists(json_path):
            json_files.append(json_path)
    
    print(f"Found {len(json_files)} JSON files for successful domains in {profile}")

    # Process each JSON file
    for json_file in tqdm(json_files, desc=f"Analyzing files for {profile}"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
                # Check domain_analysis section
                if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                    for domain_entry in data['domain_analysis']['domains']:
                        if domain_entry.get('cname_cloaking', False):
                            domain = domain_entry.get('domain', '')
                            cloaked_domains[domain] += 1
                            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    return cloaked_domains

def plot_cloaked_domains(cloaked_domains):
    """Create a horizontal bar plot of cloaked domains."""
    # Sort domains by frequency
    sorted_domains = sorted(cloaked_domains.items(), key=lambda x: x[1], reverse=True)
    domains = [d[0] for d in sorted_domains]
    frequencies = [d[1] for d in sorted_domains]
    
    # Take top 8 domains for visualization
    domains = domains[:8]
    frequencies = frequencies[:8]
    
    # Create horizontal bar plot
    plt.figure(figsize=(12, 6))
    y_pos = range(len(domains))
    plt.barh(y_pos, frequencies, color='lightblue', height=0.4)
    
    # Customize the plot
    plt.yticks(y_pos, domains)
    plt.xlabel('# of cloaked trackers')

    # Add value labels on the bars
    for i, v in enumerate(frequencies):
        plt.text(v, i, f' {v}', va='center')
    
    # Add gridlines
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.savefig('analysis/graphs/cname_cloaked_domains.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    # Get domains that loaded successfully across all profiles
    successful_domains = get_successful_domains()
    
    # Analyze CNAME cloaking for successful domains
    cloaked_domains = analyze_cname_cloaking(successful_domains=successful_domains)
    
    # Print total count
    total_instances = sum(cloaked_domains.values())
    total_unique_domains = len(cloaked_domains)
    print(f"\nTotal CNAME-cloaked domains found: {total_unique_domains}")
    print(f"Total cloaking instances: {total_instances}")
    
    # Print detailed results
    print("\nCNAME-cloaked domains found:")
    for domain, count in sorted(cloaked_domains.items(), key=lambda x: x[1], reverse=True):
        print(f"{domain}: {count} instances")
    
    # Create visualization
    if cloaked_domains:
        plot_cloaked_domains(cloaked_domains)
    else:
        print("No CNAME-cloaked domains found.")
