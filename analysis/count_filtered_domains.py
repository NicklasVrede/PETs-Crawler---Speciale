import pandas as pd
import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Define rank buckets to match sampling buckets
RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

def get_bucket_label(rank):
    for start, end in RANK_BUCKETS:
        if start <= rank <= end:
            return f"{start:,}-{end:,}"
    return "Unknown"

def analyze_bucket_distribution(df, message):
    print(f"\n{message}")
    bucket_counts = {}
    for start, end in RANK_BUCKETS:
        mask = (df['rank'] >= start) & (df['rank'] <= end)
        count = len(df[mask]['domain'].unique())
        bucket_counts[f"{start:,}-{end:,}"] = count
        print(f"Bucket [{start:,}-{end:,}]: {count} domains")
    return bucket_counts

# Load the dataset
df = pd.read_csv("data/csv/final_data.csv")

# Print initial counts and bucket distribution
print(f"Total entries before filtering: {len(df)}")
print(f"Total unique domains before filtering: {df['domain'].nunique()}")
print(f"Total profiles: {df['profile'].nunique()}")
initial_buckets = analyze_bucket_distribution(df, "Initial bucket distribution:")

# Filter for successful page loads
df_loaded = df[df['page_status'] == 'loaded']
print(f"\nEntries after loading filter: {len(df_loaded)}")
print(f"Domains after loading filter: {df_loaded['domain'].nunique()}")
loaded_buckets = analyze_bucket_distribution(df_loaded, "Bucket distribution after loading filter:")

# Get domains that loaded successfully across all profiles
all_profiles = df_loaded['profile'].unique()
successful_domains = set()
for domain in df_loaded['domain'].unique():
    if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
           for profile in all_profiles):
        successful_domains.add(domain)

# Filter for only those domains
df_final = df_loaded[df_loaded['domain'].isin(successful_domains)]

print(f"\nFinal entries after domain consistency filter: {len(df_final)}")
print(f"Final unique domains: {len(successful_domains)}")
final_buckets = analyze_bucket_distribution(df_final, "Final bucket distribution:")

# Calculate and display percentage retention for each bucket
print("\nPercentage of domains retained in each bucket:")
for bucket in initial_buckets.keys():
    initial = initial_buckets[bucket]
    final = final_buckets[bucket]
    if initial > 0:
        retention = (final / initial) * 100
        print(f"Bucket [{bucket}]: {retention:.1f}% retained ({final}/{initial})")

# Print per-profile statistics
print("\nPer-profile statistics after all filtering:")
for profile in sorted(all_profiles):
    display_name = DISPLAY_NAMES.get(profile, profile)
    profile_data = df_final[df_final['profile'] == profile]
    print(f"\n{display_name}:")
    print(f"  Total entries: {len(profile_data)}")
    print(f"  Average requests per domain: {profile_data['total_requests'].mean():.2f}")
    print(f"  Total requests: {profile_data['total_requests'].sum()}") 