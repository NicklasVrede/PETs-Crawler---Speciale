import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Load and prepare the data (same as original script)
df = pd.read_csv("data/csv/final_data2.csv")
df_loaded = df[df['page_status'] == 'loaded']

# Get domains that loaded successfully across all profiles
all_profiles = df_loaded['profile'].unique()
successful_domains = set()
for domain in df_loaded['domain'].unique():
    if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
           for profile in all_profiles):
        successful_domains.add(domain)

df_loaded = df_loaded[df_loaded['domain'].isin(successful_domains)]

# Flatten and order the profiles according to groups
ordered_profiles = []
for group_profiles in PROFILE_GROUPS.values():
    ordered_profiles.extend(group_profiles)
all_profiles = [p for p in ordered_profiles if p in df_loaded['profile'].unique()]

# 1. Original Box Plot with Log Scale
plt.figure(figsize=(16, 8))
sns.boxplot(data=df_loaded, x='profile', y='shared_identifiers_count', 
            order=all_profiles,
            color='white',
            flierprops={'marker': '.', 'markerfacecolor': 'black', 'markersize': 4})
plt.yscale('log')
plt.title('Distribution of First Party Tracking Cookies (Log Scale)')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('analysis/graphs/first_party_cookies_log_scale.png', dpi=300, bbox_inches='tight')
plt.close()

# 2. Two-Panel Approach
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), height_ratios=[2, 1])

# Top panel: Full range
sns.boxplot(data=df_loaded, x='profile', y='shared_identifiers_count', 
            order=all_profiles, ax=ax1)
ax1.set_xticklabels([])
ax1.set_title('Full Range Distribution')

# Bottom panel: Zoomed in
sns.boxplot(data=df_loaded, x='profile', y='shared_identifiers_count', 
            order=all_profiles, ax=ax2)
ax2.set_ylim(0, 5)
ax2.set_xticklabels([DISPLAY_NAMES.get(p, p) for p in all_profiles], rotation=45, ha='right')
ax2.set_title('Zoomed View (0-5 range)')

plt.suptitle('Distribution of First Party Tracking Cookies - Two-Panel View')
plt.tight_layout()
plt.savefig('analysis/graphs/first_party_cookies_two_panel.png', dpi=300, bbox_inches='tight')
plt.close()

# 3. Stacked Bar Chart
def categorize_count(x):
    if x == 0: return '0'
    elif x <= 2: return '1-2'
    elif x <= 5: return '3-5'
    elif x <= 10: return '6-10'
    else: return '10+'

df_loaded['cookie_category'] = df_loaded['shared_identifiers_count'].apply(categorize_count)
proportions = pd.crosstab(df_loaded['profile'], 
                         df_loaded['cookie_category'], 
                         normalize='index') * 100

plt.figure(figsize=(16, 8))
ax = proportions.plot(kind='bar', stacked=True)
plt.title('Distribution of First Party Tracking Cookie Counts by Profile')
plt.xlabel('Browser Profile')
plt.ylabel('Percentage of Domains')
plt.legend(title='Cookie Count Range')
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(p, p) for p in all_profiles],
          rotation=45, ha='right')
plt.tight_layout()
plt.savefig('analysis/graphs/first_party_cookies_stacked_bars.png', dpi=300, bbox_inches='tight')
plt.close()

# 4. Violin Plot with proper naming and ordering
plt.figure(figsize=(16, 8))

# Create violin plot with ordered profiles
sns.violinplot(data=df_loaded, x='profile', y='shared_identifiers_count',
               order=all_profiles, cut=0)

# Customize the plot
plt.title('Distribution of First Party Tracking Cookies per Profile', fontsize=16, pad=20)
plt.ylabel('Number of First Party Tracking Cookies', fontsize=14)
plt.xlabel('Browser Profile', fontsize=14)

# Use display names for x-tick labels
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(p, p) for p in all_profiles],
          rotation=45, ha='right', fontsize=10)

# Add group labels above the plot
y_max = df_loaded['shared_identifiers_count'].max()
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

# Add grid for better readability
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Adjust layout
plt.subplots_adjust(bottom=0.2)

# Save the plot
plt.savefig('analysis/graphs/first_party_cookies_violin.png', dpi=300, bbox_inches='tight')
plt.close()

# Print summary statistics
print("\nSummary Statistics for Each Profile:")
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]['shared_identifiers_count']
    print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
    print(f"  Zero cookies: {(profile_data == 0).mean()*100:.1f}%")
    print(f"  Median: {profile_data.median():.1f}")
    print(f"  Mean: {profile_data.mean():.1f}")
    print(f"  Max: {profile_data.max():.1f}") 