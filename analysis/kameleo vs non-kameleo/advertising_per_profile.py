import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Set font sizes
plt.rcParams.update({
    'font.size': 12,
    'axes.labelsize': 14,
    'axes.titlesize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 12
})

# Modified PROFILE_GROUPS for our legacy dataset
LEGACY_PROFILE_GROUPS = {
    "Baseline Profile": ["no_extensions"],
    
    "Traditional PETs": [
        "adblock", "adblock_plus", "disconnect", 
        "privacy_badger", "ublock", "ublock_origin_lite", "adguard",
        "ghostery_tracker_&_ad_blocker"
    ],
    
    "Cookie Extensions": [
        "accept_all_cookies", "cookie_cutter", 
        "consent_o_matic_opt_in", "consent_o_matic_opt_out", 
        "i_dont_care_about_cookies", 
        "super_agent"  # Only one super_agent profile
    ],
    
    "Other": ["decentraleyes"]
}

# Add super_agent to the display names mapping
DISPLAY_NAMES_LEGACY = DISPLAY_NAMES.copy()
DISPLAY_NAMES_LEGACY['super_agent'] = 'Super Agent'

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
        if len(sources_present) != 2:
            continue
            
        # Check if loaded in all profiles for both sources
        for source in ['kameleo', 'non-kameleo']:
            source_data = domain_data[domain_data['source'] == source]
            source_profiles = source_data['profile'].unique()
            
            if not all(source_data[source_data['profile'] == profile]['page_status'].iloc[0] == 'loaded'
                      for profile in source_profiles):
                break
        else:
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

# Flatten and order the profiles according to legacy groups
ordered_profiles = []
for group_profiles in LEGACY_PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Calculate per-profile statistics
kameleo_profile_stats = kameleo_successful.groupby('profile')['advertising_requests'].sum().reindex(ordered_profiles).reset_index()
non_kameleo_profile_stats = non_kameleo_successful.groupby('profile')['advertising_requests'].sum().reindex(ordered_profiles).reset_index()

# Map profile names to display names
kameleo_profile_stats['display_name'] = kameleo_profile_stats['profile'].map(DISPLAY_NAMES_LEGACY)
non_kameleo_profile_stats['display_name'] = non_kameleo_profile_stats['profile'].map(DISPLAY_NAMES_LEGACY)

# After reading the data but before plotting
print("\nAvailable profiles in kameleo dataset:")
print(sorted(kameleo_successful['profile'].unique()))

print("\nAvailable profiles in non-kameleo dataset:")
print(sorted(non_kameleo_successful['profile'].unique()))

print("\nOrdered profiles we're using:")
print(ordered_profiles)

# Also print the display names mapping for these profiles
print("\nDisplay names mapping:")
for profile in ordered_profiles:
    print(f"{profile} -> {DISPLAY_NAMES_LEGACY.get(profile, profile)}")

# Create figure
fig, ax = plt.subplots(figsize=(15, 6))

# Plot advertising requests per profile
x = np.arange(len(kameleo_profile_stats))
width = 0.35

plt.bar(x - width/2, kameleo_profile_stats['advertising_requests'], 
        width, label='kameleo', color='#2ecc71')
plt.bar(x + width/2, non_kameleo_profile_stats['advertising_requests'], 
        width, label='non-kameleo', color='#3498db')

# Add group labels and separators
y_max = max(kameleo_profile_stats['advertising_requests'].max(), 
            non_kameleo_profile_stats['advertising_requests'].max())
current_position = 0
for group_name, group_profiles in LEGACY_PROFILE_GROUPS.items():
    if group_profiles:
        group_size = len(group_profiles)
        group_center = current_position + group_size / 2 - 0.5
        
        # Add group label
        plt.text(group_center, y_max * 1.05, group_name,
                ha='center', va='bottom', fontsize=12,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
        
        # Add separator line
        if current_position + group_size < len(ordered_profiles):
            plt.axvline(x=current_position + group_size - 0.5, color='black', 
                       linestyle=':', alpha=0.7)
        
        current_position += group_size

plt.ylabel('# advertising requests')
plt.xlabel('')
plt.xticks(x, kameleo_profile_stats['display_name'], rotation=45, ha='right')
plt.legend()

# Adjust layout
plt.subplots_adjust(bottom=0.2, top=0.85)

# Save the plot
plt.savefig('analysis/graphs/kameleo vs non-kameleo/advertising_requests_per_profile.png', 
            bbox_inches='tight', dpi=300)
plt.close()

# Print average statistics
print("\nAverage advertising requests per profile:")
print(f"Kameleo: {kameleo_profile_stats['advertising_requests'].mean():.1f}")
print(f"Non-Kameleo: {non_kameleo_profile_stats['advertising_requests'].mean():.1f}") 