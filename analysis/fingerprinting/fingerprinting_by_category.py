import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Use the 4 fingerprinting methods from available columns
fingerprinting_cols = [
    "canvas_fingerprinting_calls",    # Canvas
    "media_fingerprinting_calls",     # AudioContext
    "hardware_fingerprinting_calls",  # WebRTC
    "webgl_fingerprinting_calls"      # Canvas Font
]

# Define colors for fingerprinting categories
fp_colors = [
    "#4286f4",  # Canvas - blue
    "#f79646",  # AudioContext - orange
    "#4ba651",  # WebRTC - green
    "#de2d26",  # Canvas Font - red
]

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

# Calculate fingerprinting type counts for each profile
g = df_loaded.groupby("profile")[fingerprinting_cols].sum()

# Reindex to get the desired order
g = g.reindex(all_profiles)

# Create the plot
fig, ax = plt.subplots(figsize=(16, 8))

# Set the width of each bar and positions of the bars
width = 0.2
x = np.arange(len(all_profiles))

# Create grouped bars
for i, (col, color) in enumerate(zip(fingerprinting_cols, fp_colors)):
    values = g[col]
    offset = width * (i - 1.5)
    ax.bar(x + offset, values, width, label=col.replace('_fingerprinting_calls', '').replace('_', ' ').title(),
           color=color)

# Add reference lines for baseline profile values
baseline_values = g.loc['no_extensions']
for (col, color), baseline_value in zip(zip(fingerprinting_cols, fp_colors), baseline_values):
    ax.axhline(y=baseline_value, color=color, linestyle='--', alpha=0.3, zorder=1)

# Add group labels above the plot
y_max = g.max().max()
current_position = 0
for group_name, group_profiles in PROFILE_GROUPS.items():
    group_profiles_in_data = [p for p in group_profiles if p in all_profiles]
    if group_profiles_in_data:
        group_start = current_position
        group_end = current_position + len(group_profiles_in_data) - 1
        
        # Place the group label in the middle of the group
        label_position = (group_start + group_end) / 2
        plt.text(label_position, y_max * 1, group_name,
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
plt.ylabel('Number of Fingerprinting Calls', fontsize=14, labelpad=10)
plt.xlabel('', fontsize=14, labelpad=10)
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Format legend labels with proper colors and style
legend_labels = ["Canvas", "AudioContext", "WebRTC", "Canvas Font"]
handles = [plt.Rectangle((0,0),1,1, color=color) for color in fp_colors]  # Create colored rectangles
ax.legend(handles, legend_labels, bbox_to_anchor=(0.02, 0.95), loc='upper left')

# Use display names for x-tick labels
plt.xticks(x, [DISPLAY_NAMES.get(profile, profile) for profile in all_profiles],
           rotation=45, ha='right', fontsize=10)

# Adjust layout
plt.subplots_adjust(bottom=0.25, top=0.85)

# Save and show the plot
plt.savefig('analysis/graphs/fingerprinting_methods_distribution.png', dpi=300, bbox_inches='tight')
plt.show()

# Print statistics
print("\nFingerprinting Statistics:")
for profile in all_profiles:
    profile_data = g.loc[profile]
    total = profile_data.sum()
    print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
    print(f"  Total calls: {int(total)}")
    for method in fingerprinting_cols:
        method_name = method.replace('_fingerprinting_calls', '').replace('_', ' ').title()
        value = profile_data[method]
        print(f"  {method_name}: {int(value)}") 