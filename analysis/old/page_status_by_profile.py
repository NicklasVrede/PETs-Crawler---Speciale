import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load the dataset
df = pd.read_csv("data/csv/trial02.csv")

# Order the profiles in a meaningful way
ordered_profiles = [
    # No extensions first
    "no_extensions",
    
    # Adblockers
    "adblock", "adblock_plus", "adguard", "disconnect", 
    "ghostery_tracker_&_ad_blocker", "privacy_badger", 
    "ublock", "ublock_origin_lite",
    
    # Cookie banner extensions
    "accept_all_cookies", "cookie_cutter", 
    "consent_o_matic_opt_in", "consent_o_matic_opt_out", 
    "i_dont_care_about_cookies", "super_agent",
    
    # Other types of extensions
    "decentraleyes"
]

# Ensure that the page_status column exists
if 'page_status' not in df.columns:
    print("Error: 'page_status' column not found in the dataset")
    # Check if there's a similar column that might contain page status
    possible_columns = [col for col in df.columns if 'page' in col.lower() and 'status' in col.lower()]
    if possible_columns:
        print(f"Similar columns found: {possible_columns}")
    exit()

# Calculate counts for each profile and status
status_counts = df.groupby(['profile', 'page_status']).size().unstack(fill_value=0)

# Remove "loaded" status as per request (if it exists)
if 'loaded' in status_counts.columns:
    status_counts = status_counts.drop('loaded', axis=1)

# Reindex to ensure all profiles are included in the desired order
available_profiles = [p for p in ordered_profiles if p in status_counts.index]
status_counts = status_counts.reindex(available_profiles)

# Create a stacked bar chart
fig, ax = plt.subplots(figsize=(14, 8))
x = np.arange(len(status_counts.index))

# Plot each status as a stacked bar using default colors
bottom = np.zeros(len(status_counts.index))
for status in status_counts.columns:
    bars = ax.bar(x, status_counts[status], bottom=bottom, label=status)
    
    # Add count labels inside the bars (only for bars with count > 1)
    for i, bar in enumerate(bars):
        height = bar.get_height()
        if height > 1:  # Only show label if bar has meaningful count
            ax.text(
                bar.get_x() + bar.get_width()/2., 
                bottom[i] + height/2,
                f"{int(height)}", 
                ha='center', va='center', 
                color='white', fontsize=8
            )
    
    bottom += status_counts[status].values

# Add labels and title
ax.set_ylabel('Number of Pages')
ax.set_title('Page Status Distribution by Browser Profile')
ax.set_xticks(x)
ax.set_xticklabels(status_counts.index, rotation=45, ha='right')

# Set y-axis limit based only on the visible data (excluding loaded)
y_max = status_counts.sum(axis=1).max()
ax.set_ylim(0, y_max * 1.1)  # Add 10% margin above the highest bar

# Add a grid for better readability
ax.grid(axis='y', linestyle='--', alpha=0.3)

# Add a legend
ax.legend(title='Page Status', bbox_to_anchor=(1.05, 1), loc='upper left')

# Add total sample size as a text label for each profile (excluding loaded)
for i, profile in enumerate(status_counts.index):
    profile_count = status_counts.loc[profile].sum()
    ax.text(
        i, -1, 
        f"n={profile_count}", 
        ha='center', va='top', fontsize=8
    )

plt.tight_layout()
plt.savefig('page_status_by_profile.png', dpi=300, bbox_inches='tight')
plt.show()