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

# Function to identify outliers for a group
def get_outliers(group_data):
    q1 = group_data['unique_cookies'].quantile(0.25)
    q3 = group_data['unique_cookies'].quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    return group_data[group_data['unique_cookies'] > upper_bound]

# Create the box plot
plt.figure(figsize=(16, 10))

# Create box plot with black and white style
sns.boxplot(data=df_loaded, x='profile', y='unique_cookies', 
            order=all_profiles,
            color='white',          
            flierprops={'marker': '.', 'markerfacecolor': 'black', 'markersize': 4},  
            medianprops={'color': 'black'},  
            boxprops={'edgecolor': 'black'},  
            whiskerprops={'color': 'black'},  
            capprops={'color': 'black'},      
            showfliers=False,  # Changed to False to hide outliers
            whis=1.5)        

# Define a softer red color
mean_color = '#E68080'  # Light coral red
# Alternative options: '#CD5C5C' (Indian Red) or '#E68080' (Soft red)

# Add median and mean annotations for each profile
for i, profile in enumerate(all_profiles):
    profile_data = df_loaded[df_loaded['profile'] == profile]['unique_cookies']
    median = profile_data.median()
    mean = profile_data.mean()
    
    # Annotate median 
    plt.text(i+ 0.17, median - 3.75, f'{median:.1f}',
             ha='right', va='bottom', fontsize=12, fontweight='bold')
    
    # Show mean with a dashed line across the box
    plt.plot([i-0.4, i+0.4], [mean, mean], '--', 
             color=mean_color, 
             linewidth=1, 
             alpha=0.8)
    
    # Annotate mean value
    plt.text(i + 0.17, mean, f'{mean:.1f}',
             ha='right', va='bottom', fontsize=12, color=mean_color, fontweight='bold')

# Add group labels above the plot
y_max = plt.ylim()[1]  # Get the current y-axis limit
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group, much closer to the plot
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1.05,
                group_name,
                ha='center', va='bottom', fontsize=14,
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
plt.ylabel('Number of Cookies', fontsize=16, labelpad=10)
plt.xlabel('')
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Use display names for x-tick labels
plt.xticks(range(len(all_profiles)), 
          [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
          rotation=45, ha='right', fontsize=14)

# Adjust layout with even less space at the top
plt.subplots_adjust(bottom=0.2, top=0.95)

# Adjust y-axis limit to be lower
q1 = df_loaded['unique_cookies'].quantile(0.25)
q3 = df_loaded['unique_cookies'].quantile(0.75)
iqr = q3 - q1
upper_bound = q3 + 4 * iqr
y_max = min(upper_bound, 150)
plt.ylim(-2, y_max)

# Update legend for mean marker
plt.plot([], [], '--', color=mean_color, label='Mean', alpha=0.8)
plt.legend(loc='upper right', bbox_to_anchor=(1, 0.95), fontsize=14)
plt.yticks(fontsize=14)

# Save and show the plot
plt.savefig('analysis/graphs/cookies_per_page_with_different_profiles.png', dpi=300, bbox_inches='tight')
plt.show()

# Print summary statistics
print("\nSummary Statistics:")
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]['unique_cookies']
    print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
    print(f"  Median: {profile_data.median():.1f}")
    print(f"  Mean: {profile_data.mean():.1f}")
    print(f"  Q1: {profile_data.quantile(0.25):.1f}")
    print(f"  Q3: {profile_data.quantile(0.75):.1f}")
    print(f"  Min: {profile_data.min():.1f}")
    print(f"  Max: {profile_data.max():.1f}")

# Print all outliers for reference
print("\nOutliers (domains with unusually high cookie counts):")
for profile in all_profiles:
    profile_data = df_loaded[df_loaded['profile'] == profile]
    outliers = get_outliers(profile_data)
    
    if not outliers.empty:
        print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
        for _, row in outliers.sort_values('unique_cookies', ascending=False).iterrows():
            print(f"  {row['domain']}: {int(row['unique_cookies'])} cookies") 