import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']

# Define rank buckets (same as in other analyses)
RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

def get_rank_bucket_label(rank):
    """Convert a rank to a bucket label"""
    for start, end in RANK_BUCKETS:
        if start <= rank <= end:
            if start < 1000:
                start_label = str(start)
            else:
                start_label = f"{start//1000}k"
            if end < 1000:
                end_label = str(end)
            else:
                end_label = f"{end//1000}k"
            return f"[{start_label}-{end_label}]"
    return "unknown"

# Add rank bucket column
df_loaded['rank_bucket'] = df_loaded['rank'].apply(get_rank_bucket_label)
rank_order = [get_rank_bucket_label(bucket[0]) for bucket in RANK_BUCKETS]

# Filter for only the baseline profile
baseline_df = df_loaded[df_loaded['profile'] == 'no_extensions']

# Calculate average first-party tracking cookies per rank bucket
cookies_by_rank = baseline_df.groupby('rank_bucket')['shared_identifiers_count'].agg(['mean', 'median', 'count'])
cookies_by_rank = cookies_by_rank.reindex(rank_order)  # Ensure correct order

# Create a more comprehensive figure with both mean and median
plt.figure(figsize=(12, 8))

# Create bar chart with mean values (primary)
x = np.arange(len(cookies_by_rank))
width = 0.35
mean_bars = plt.bar(x - width/2, cookies_by_rank['mean'], width, label='Mean', color='steelblue', alpha=0.8)
median_bars = plt.bar(x + width/2, cookies_by_rank['median'], width, label='Median', color='lightsteelblue', alpha=0.8)

# Add value labels
for bars, values in [(mean_bars, cookies_by_rank['mean']), (median_bars, cookies_by_rank['median'])]:
    for i, bar in enumerate(bars):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, height + 0.1,
                f'{height:.2f}', ha='center', va='bottom', fontsize=9)

# Add count labels below each group
for i, count in enumerate(cookies_by_rank['count']):
    plt.text(i, -0.2, f'n={count}', ha='center', va='top', fontsize=9)

# Add a legend
plt.legend()

# Let's also add domain count distribution information
# Add this code to print top domains with most tracking cookies
print("\nTop 10 domains with most first-party tracking cookies:")
top_domains = baseline_df.sort_values('shared_identifiers_count', ascending=False).head(10)
for _, row in top_domains.iterrows():
    print(f"{row['domain']}: {row['shared_identifiers_count']} cookies (rank: {row['rank']})")

# Add code to print statistics about domains with zero cookies
zero_cookies = baseline_df[baseline_df['shared_identifiers_count'] == 0]
print(f"\nDomains with zero tracking cookies: {len(zero_cookies)} ({len(zero_cookies)/len(baseline_df)*100:.1f}%)")

# Customize the plot
plt.ylabel('Average Number of First-Party Tracking Cookies', fontsize=12)
plt.grid(axis='y', linestyle='--', alpha=0.3)

# Set x-tick positions and labels
plt.xticks(range(len(cookies_by_rank)), 
          [rb.replace('[', '').replace(']', '') for rb in cookies_by_rank.index],
          rotation=45, ha='right')

# Adjust layout
plt.tight_layout()

# Save the plot
plt.savefig('analysis/graphs/first_party_cookies_by_rank.png', dpi=300, bbox_inches='tight')
plt.close()

# Print summary statistics
print("\nFirst-Party Tracking Cookies by Rank Bucket (Baseline Profile):")
for bucket in cookies_by_rank.index:
    mean = cookies_by_rank.loc[bucket, 'mean']
    median = cookies_by_rank.loc[bucket, 'median']
    count = cookies_by_rank.loc[bucket, 'count']
    print(f"Rank {bucket}:")
    print(f"  Mean: {mean:.2f}")
    print(f"  Median: {median:.2f}")
    print(f"  Sample size: {count}") 