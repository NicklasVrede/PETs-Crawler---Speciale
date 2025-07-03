import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

def get_successful_domains():
    """Get domains that loaded successfully across all profiles in both datasets."""
    # Read and prepare datasets with source labels
    kameleo_df = pd.read_csv('data/csv/kameleo.csv')
    kameleo_df['source'] = 'kameleo'
    non_kameleo_df = pd.read_csv('data/csv/non-kameleo.csv')
    non_kameleo_df['source'] = 'non-kameleo'
    
    # Combine datasets
    combined_df = pd.concat([kameleo_df, non_kameleo_df])
    
    # Get successful domains for each source
    successful_domains = set()
    for domain in tqdm(combined_df['domain'].unique(), desc="Finding successful domains"):
        domain_data = combined_df[combined_df['domain'] == domain]
        
        # Check if domain loaded in both sources
        sources_present = domain_data['source'].unique()
        if len(sources_present) != 2:  # Must be present in both sources
            continue
            
        # Check if loaded in all profiles for both sources
        for source in ['kameleo', 'non-kameleo']:
            source_data = domain_data[domain_data['source'] == source]
            source_profiles = source_data['profile'].unique()
            
            # Check if all attempts for this domain in this source were successful
            if not all(source_data[source_data['profile'] == profile]['page_status'].iloc[0] == 'loaded'
                      for profile in source_profiles):
                break
        else:  # No break occurred, domain was successful in all profiles
            successful_domains.add(domain)
    
    return successful_domains

# Get successful domains
successful_domains = get_successful_domains()

# Read and prepare the data
kameleo_df = pd.read_csv('data/csv/kameleo.csv')
non_kameleo_df = pd.read_csv('data/csv/non-kameleo.csv')

# Filter for successful domains and loaded status
kameleo_successful = kameleo_df[
    (kameleo_df['domain'].isin(successful_domains)) & 
    (kameleo_df['page_status'] == 'loaded')
]
non_kameleo_successful = non_kameleo_df[
    (non_kameleo_df['domain'].isin(successful_domains)) & 
    (non_kameleo_df['page_status'] == 'loaded')
]

# Calculate sums
domains_sums = [
    kameleo_successful['advertising_domains'].sum(),
    non_kameleo_successful['advertising_domains'].sum()
]

requests_sums = [
    kameleo_successful['advertising_requests'].sum(),
    non_kameleo_successful['advertising_requests'].sum()
]

# Calculate percentage increases
domains_increase = ((domains_sums[0] - domains_sums[1]) / domains_sums[1]) * 100
requests_increase = ((requests_sums[0] - requests_sums[1]) / requests_sums[1]) * 100

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Increase space between subplots
plt.subplots_adjust(wspace=0.5)

# Plot domains (left subplot)
x = [0, 0.3]
bars1 = ax1.bar(x, domains_sums, color=['#2ecc71', '#3498db'], width=0.15)
ax1.set_ylabel('# advertising domains', fontsize=18)
ax1.set_xlabel('')
ax1.set_xticks(x)
ax1.set_xticklabels(['kameleo', 'non-kameleo'])
ax1.tick_params(axis='x', labelsize=20)
ax1.tick_params(axis='y', labelsize=18)

# Add value annotations for domains
ax1.text(x[0], domains_sums[0], f'{int(domains_sums[0]):,}', ha='center', va='bottom', fontsize=16)
ax1.text(x[0], domains_sums[0]*0.95, f'(+{domains_increase:.1f}%)', ha='center', va='top', fontsize=16)
ax1.text(x[1], domains_sums[1], f'{int(domains_sums[1]):,}', ha='center', va='bottom', fontsize=16)

# Plot requests (right subplot)
bars2 = ax2.bar(x, requests_sums, color=['#2ecc71', '#3498db'], width=0.15)
ax2.set_ylabel('# advertising requests', fontsize=18)
ax2.set_xlabel('')
ax2.set_xticks(x)
ax2.set_xticklabels(['kameleo', 'non-kameleo'])
ax2.tick_params(axis='x', labelsize=20)
ax2.tick_params(axis='y', labelsize=18)

# Add value annotations for requests
ax2.text(x[0], requests_sums[0], f'{int(requests_sums[0]):,}', ha='center', va='bottom', fontsize=16)
ax2.text(x[0], requests_sums[0]*0.95, f'(+{requests_increase:.1f}%)', ha='center', va='top', fontsize=16)
ax2.text(x[1], requests_sums[1], f'{int(requests_sums[1]):,}', ha='center', va='bottom', fontsize=16)

# Save the plot
plt.savefig('analysis/graphs/kameleo vs non-kameleo/advertising_comparison.png')
plt.close() 