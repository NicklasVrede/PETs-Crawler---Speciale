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

# Calculate total CNAME cloaking instances per profile
profile_stats = []
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]
    total_instances = profile_data['potential_cname_cloaking'].sum()
    domains_with_cloaking = len(profile_data[profile_data['potential_cname_cloaking'] > 0])
    
    profile_stats.append({
        'profile': profile,
        'total_instances': total_instances,
        'domains_with_cloaking': domains_with_cloaking
    })

# Create the bar plot
plt.figure(figsize=(16, 8))

# Create bars with smaller width (default is 0.8)
x = range(len(all_profiles))
bars = plt.bar(x, [stat['total_instances'] for stat in profile_stats], 
               color='white', 
               edgecolor='black',
               width=0.5)  # Changed from default 0.8 to 0.5

# Add value labels on top of each bar
for i, bar in enumerate(bars):
    height = bar.get_height()
    if height > 0:
        plt.text(bar.get_x() + bar.get_width()/2, height,
                f'{int(height)}', ha='center', va='bottom', fontsize=10)

# Add group labels above the plot
y_max = max(stat['total_instances'] for stat in profile_stats)
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.10, group_name,
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
plt.ylabel('Total Number of CNAME Cloaking Instances', fontsize=14, labelpad=10)
plt.xlabel('', fontsize=14, labelpad=10)
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Use display names for x-tick labels
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
          rotation=45, ha='right', fontsize=10)

# Adjust layout
plt.subplots_adjust(bottom=0.25, top=0.85)

# Save and show the plot
plt.savefig('analysis/graphs/cname_cloaking_total_instances.png', dpi=300, bbox_inches='tight')
plt.show()

# Print detailed statistics
print("\nDetailed Statistics:")
for stat in profile_stats:
    profile_name = DISPLAY_NAMES.get(stat['profile'], stat['profile'])
    print(f"\n{profile_name}:")
    print(f"  Total CNAME cloaking instances: {int(stat['total_instances'])}")
    print(f"  Number of domains with cloaking: {stat['domains_with_cloaking']}")

# Print domains with CNAME cloaking for each profile
print("\nDomains with CNAME cloaking by profile:")
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]
    cloaking_domains = profile_data[profile_data['potential_cname_cloaking'] > 0]
    
    if not cloaking_domains.empty:
        print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
        for _, row in cloaking_domains.iterrows():
            print(f"  {row['domain']}: {int(row['potential_cname_cloaking'])} instances")