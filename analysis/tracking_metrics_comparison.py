import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.ticker import MaxNLocator

# Load the dataset
df = pd.read_csv("data/csv/non-kameleo.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Get all available profiles
all_profiles = sorted(df_loaded['profile'].unique())
print(f"Found {len(all_profiles)} different browser profiles in the dataset")

# Define tracking-related metrics to analyze
tracking_metrics = [
    'potential_cname_cloaking',
    'potential_tracking_cookies_count',
    'storage_potential_identifiers_count'
]

# Check which metrics are actually in the dataset
available_metrics = [col for col in tracking_metrics if col in df_loaded.columns]
if len(available_metrics) < len(tracking_metrics):
    missing = set(tracking_metrics) - set(available_metrics)
    print(f"Warning: The following tracking metrics are not in the dataset: {', '.join(missing)}")
    tracking_metrics = available_metrics

# Find domains that loaded successfully across all profiles
# This is a strict requirement that might significantly reduce the number of domains
# We'll try to find all domains, but if there are too few, we'll relax this constraint
domains_common_to_all = set()
for profile in all_profiles:
    profile_domains = set(df_loaded[df_loaded['profile'] == profile]['domain'].unique())
    if not domains_common_to_all:
        domains_common_to_all = profile_domains
    else:
        domains_common_to_all = domains_common_to_all.intersection(profile_domains)

print(f"Found {len(domains_common_to_all)} domains that loaded successfully across all {len(all_profiles)} profiles")

# If too few domains loaded across all profiles, we might need a different approach
min_domains_threshold = 10

if len(domains_common_to_all) < min_domains_threshold:
    print("Too few domains common to all profiles. Using a different approach...")
    
    # Instead, we'll analyze all domains for each profile independently
    df_analysis = df_loaded
    
    # Create a DataFrame with the mean values for each profile and metric
    means_data = []
    
    for profile in all_profiles:
        profile_data = df_analysis[df_analysis['profile'] == profile]
        profile_domain_count = len(profile_data['domain'].unique())
        
        for metric in tracking_metrics:
            if metric in profile_data.columns:
                means_data.append({
                    'profile': profile,
                    'metric': metric,
                    'mean': profile_data[metric].mean(),
                    'domain_count': profile_domain_count
                })
        
        print(f"Profile '{profile}' has data for {profile_domain_count} domains")
else:
    # Use only the common domains
    df_analysis = df_loaded[df_loaded['domain'].isin(domains_common_to_all)]
    
    # Create a DataFrame with the mean values for each profile and metric
    means_data = []
    
    for profile in all_profiles:
        profile_data = df_analysis[df_analysis['profile'] == profile]
        
        for metric in tracking_metrics:
            if metric in profile_data.columns:
                means_data.append({
                    'profile': profile,
                    'metric': metric,
                    'mean': profile_data[metric].mean(),
                    'domain_count': len(domains_common_to_all)
                })

means_df = pd.DataFrame(means_data)

# Create friendly labels for metrics
metric_labels = {
    'potential_cname_cloaking': 'Potential CNAME Cloaking',
    'potential_tracking_cookies_count': 'Potential Tracking Cookies',
    'storage_potential_identifiers_count': 'Storage Potential Identifiers'
}

# Group profiles into categories for better visualization
profile_categories = {
    'no_extensions': 'No Extensions',
    
    # Ad blockers
    'adblock_plus': 'Ad Blockers',
    'disconnect': 'Ad Blockers',
    'privacy_badger': 'Ad Blockers',
    'ublock': 'Ad Blockers',
    'ublock_origin_lite': 'Ad Blockers',
    'adguard': 'Ad Blockers',
    
    # Cookie managers
    'accept_all_cookies': 'Cookie Managers',
    'cookie_cutter': 'Cookie Managers',
    'consent_o_matic_opt_in': 'Cookie Managers',
    'consent_o_matic_opt_out': 'Cookie Managers',
    
    # Other categories
    'ghostery_s_ad_blocker': 'Other',
    'i_dont_care_about_cookies': 'Other',
    'super_agent': 'Other',
    'decentraleyes': 'Other'
}

# Add a category column to the DataFrame
means_df['category'] = means_df['profile'].apply(
    lambda x: profile_categories.get(x, 'Other')
)

# Create individual bar charts for each metric
for metric in tracking_metrics:
    plt.figure(figsize=(16, 10))
    
    # Filter data for this metric
    metric_data = means_df[means_df['metric'] == metric].sort_values(by='mean')
    
    # Create color mapping based on profile categories
    category_colors = {
        'No Extensions': '#1f77b4',  # blue
        'Ad Blockers': '#ff7f0e',    # orange
        'Cookie Managers': '#2ca02c', # green
        'Other': '#d62728'           # red
    }
    
    # Create the bar colors based on categories
    bar_colors = [category_colors[cat] for cat in metric_data['category']]
    
    # Create the bar chart
    bars = plt.bar(range(len(metric_data)), metric_data['mean'], color=bar_colors, alpha=0.8)
    
    # Add value labels on top of each bar
    for i, bar in enumerate(bars):
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2, height + 0.02 * metric_data['mean'].max(),
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9, rotation=0)
    
    # Customize the plot
    metric_label = metric_labels.get(metric, metric.replace('_', ' ').title())
    plt.title(f'{metric_label} Comparison Across All Profiles', fontsize=16, pad=20)
    plt.ylabel('Average Count', fontsize=14)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Add x-tick labels with profile names
    plt.xticks(range(len(metric_data)), metric_data['profile'], rotation=45, ha='right')
    
    # Add a legend for profile categories
    handles = [plt.Rectangle((0,0),1,1, color=color, alpha=0.8) for color in category_colors.values()]
    plt.legend(handles, category_colors.keys(), title="Profile Category", loc="upper left")
    
    plt.tight_layout()
    plt.savefig(f'all_profiles_{metric}_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()

# Create a heatmap for all metrics and profiles
plt.figure(figsize=(18, 10))

# Create a pivot table for the heatmap
heatmap_data = means_df.pivot(index='profile', columns='metric', values='mean')

# Sort rows by one of the metrics (e.g., tracking cookies) to reveal patterns
if 'potential_tracking_cookies_count' in heatmap_data.columns:
    heatmap_data = heatmap_data.sort_values(by='potential_tracking_cookies_count')

# Create the heatmap
ax = sns.heatmap(heatmap_data, annot=True, fmt='.1f', cmap='YlOrRd', linewidths=.5)

# Rename columns for better readability
ax.set_xticklabels([metric_labels.get(label, label.replace('_', ' ').title()) for label in heatmap_data.columns], 
                   rotation=45, ha='right')

plt.title('Tracking Metrics Heatmap Across All Profiles', fontsize=16, pad=20)
plt.tight_layout()
plt.savefig('all_profiles_tracking_metrics_heatmap.png', dpi=300, bbox_inches='tight')
plt.show()

# Create a grouped bar chart
plt.figure(figsize=(18, 10))

# Group by category and calculate the mean for each metric
category_means = means_df.groupby(['category', 'metric'])['mean'].mean().reset_index()

# Create a pivot table for easier plotting
pivot_data = category_means.pivot(index='category', columns='metric', values='mean')

# Plot grouped bars
pivot_data.plot(kind='bar', figsize=(16, 8), width=0.8)

# Customize the plot
plt.title('Average Tracking Metrics by Profile Category', fontsize=16, pad=20)
plt.ylabel('Average Count', fontsize=14)
plt.xlabel('Profile Category', fontsize=14)
plt.grid(axis='y', linestyle='--', alpha=0.3)
plt.legend(title='Tracking Metric', labels=[metric_labels.get(col, col.replace('_', ' ').title()) 
                                          for col in pivot_data.columns])
plt.tight_layout()
plt.savefig('tracking_metrics_by_category.png', dpi=300, bbox_inches='tight')
plt.show()

# Print out the top 3 best and worst profiles for each metric
print("\nTop and Bottom Performers for Each Metric:")

for metric in tracking_metrics:
    metric_data = means_df[means_df['metric'] == metric].sort_values(by='mean')
    metric_name = metric_labels.get(metric, metric.replace('_', ' ').title())
    
    print(f"\n{metric_name}:")
    print("  Best Performers (Lowest Values):")
    for i, row in metric_data.head(3).iterrows():
        print(f"    {row['profile']}: {row['mean']:.2f}")
    
    print("  Worst Performers (Highest Values):")
    for i, row in metric_data.tail(3).iterrows():
        print(f"    {row['profile']}: {row['mean']:.2f}") 