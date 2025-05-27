import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Get domains that loaded successfully across all profiles
all_profiles = df_loaded['profile'].unique()
successful_domains = set()
for domain in df_loaded['domain'].unique():
    if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
           for profile in all_profiles):
        successful_domains.add(domain)

# Filter for only those domains
df_loaded = df_loaded[df_loaded['domain'].isin(successful_domains)]

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)

# Ensure we only use profiles that exist in our data
all_profiles = [p for p in ordered_profiles if p in df_loaded['profile'].unique()]

# Create the violin plot
plt.figure(figsize=(16, 8))

# Create violin plot with default seaborn colors and adjusted width
sns.violinplot(data=df_loaded, x='profile', y='shared_identifiers_count',
               order=all_profiles,
               inner='box',    # Show box plot inside violin
               cut=0,         # Cut off violin at observed data limits
               width=0.9)     # Adjust width (default is 0.8, smaller number = narrower violins)

# Calculate y_max first before using it
y_max = df_loaded['shared_identifiers_count'].max()

# Add small n=XXX counts below each violin but moved up slightly
for idx, profile in enumerate(all_profiles):
    profile_total = df_loaded[df_loaded['profile'] == profile]['shared_identifiers_count'].sum()
    plt.text(idx, -0.5,  # Moved up from -0.8 to -0.5
             f'n={profile_total:,.0f}',
             ha='center', va='top', fontsize=8)

# Add group labels above the plot but moved down slightly
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group (moved lower)
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.1,  # Reduced from 1.25 to 1.1
                group_name,
                ha='center', va='bottom', fontsize=12,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
        
        current_position += len(group_profiles_in_data)

# Add vertical lines to separate groups
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        current_position += len(group_profiles_in_data)
        if current_position < len(all_profiles):
            plt.axvline(x=current_position - 0.5, color='black', linestyle=':', alpha=0.7)

# Customize the plot
plt.ylabel('Number of First Party Tracking Cookies', fontsize=14, labelpad=10)
plt.xlabel('', fontsize=14, labelpad=10)
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Use display names for x-tick labels
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
          rotation=45, ha='right', fontsize=10)


# Adjust layout (increased top margin to accommodate labels)
plt.subplots_adjust(bottom=0.2, top=0.8)

# Save the plot
plt.savefig('analysis/graphs/first_party_cookies_violin.png', dpi=300, bbox_inches='tight')
plt.close()

# Calculate and print total cookies per profile before summary statistics
print("\nTotal First Party Tracking Cookies per Profile:")
for profile in all_profiles:
    profile_total = df_loaded[df_loaded['profile'] == profile]['shared_identifiers_count'].sum()
    print(f"{DISPLAY_NAMES.get(profile, profile)}: {profile_total:,.0f}")

# Calculate and print total cookies before summary statistics
total_cookies = df_loaded['shared_identifiers_count'].sum()
print(f"\nTotal First Party Tracking Cookies (all profiles): {total_cookies:,.0f}")

# Print summary statistics
print("\nSummary Statistics:")
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]['shared_identifiers_count']
    print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
    print(f"  Median: {profile_data.median():.1f}")
    print(f"  Mean: {profile_data.mean():.1f}")
    print(f"  Q1: {profile_data.quantile(0.25):.1f}")
    print(f"  Q3: {profile_data.quantile(0.75):.1f}")
    print(f"  Min: {profile_data.min():.1f}")
    print(f"  Max: {profile_data.max():.1f}") 