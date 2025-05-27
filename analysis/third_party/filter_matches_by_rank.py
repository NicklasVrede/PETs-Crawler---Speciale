import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.colors import rgb2hex
from tqdm import tqdm

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Define rank buckets (same as in other analysis)
RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

# Get colors from the tab20 colormap
colors = [rgb2hex(plt.cm.tab20(i)) for i in range(20)]

# Define specific markers and colors for each profile using tab20 colors
profile_styles = {
    'accept_all_cookies': {'marker': 'o', 'color': colors[0]},      # tab20 blue
    'adblock': {'marker': '^', 'color': colors[2]},                # tab20 green
    'adblock_plus': {'marker': '^', 'color': colors[4]},          # tab20 red
    'adguard': {'marker': 'D', 'color': colors[6]},               # tab20 purple
    'consent_o_matic_opt_in': {'marker': 'v', 'color': colors[8]},  # tab20 brown
    'consent_o_matic_opt_out': {'marker': 'v', 'color': colors[10]}, # tab20 pink
    'decentraleyes': {'marker': '>', 'color': colors[12]},          # tab20 gray
    'disconnect': {'marker': 's', 'color': colors[13]},             # New style for Disconnect
    'ghostery_tracker_&_ad_blocker': {'marker': 'o', 'color': colors[14]},  # tab20 olive
    'ghostery_tracker_&_ad_blocker_only_never_consent': {'marker': 'o', 'color': colors[16]},  # tab20 cyan
    'i_dont_care_about_cookies': {'marker': 'o', 'color': colors[18]},  # tab20 lime
    'no_extensions': {'marker': 'o', 'color': 'black'},            # Black (Baseline)
    'privacy_badger': {'marker': '*', 'color': colors[1]},         # tab20 light blue
    'super_agent_opt_in': {'marker': 'o', 'color': colors[3]},     # tab20 light green
    'super_agent_opt_out': {'marker': 'o', 'color': colors[5]},    # tab20 light red
    'ublock': {'marker': '+', 'color': colors[7]},                # tab20 light purple
    'ublock_origin_lite': {'marker': 'x', 'color': colors[15]},    # New style for uBlock Origin Lite
}

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

def get_successful_domains(csv_path="data/csv/final_data2.csv"):
    """Get domains that loaded successfully across all profiles."""
    df = pd.read_csv(csv_path)
    df_loaded = df[df['page_status'] == 'loaded']
    all_profiles = df_loaded['profile'].unique()
    successful_domains = set()
    
    for domain in tqdm(df_loaded['domain'].unique(), desc="Finding successful domains"):
        if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
               for profile in all_profiles):
            successful_domains.add(domain)
    
    return successful_domains

def analyze_filter_matches():
    # Load the dataset
    df = pd.read_csv("data/csv/final_data2.csv")
    
    # Get domains that loaded successfully across all profiles
    successful_domains = get_successful_domains()
    
    # Filter for successful page loads and successful domains
    df = df[
        (df['page_status'] == 'loaded') & 
        (df['domain'].isin(successful_domains))
    ]
    
    # Add rank bucket column
    df['rank_bucket'] = df['rank'].apply(get_rank_bucket_label)
    
    # Calculate average filter matches per rank bucket for each profile
    results = defaultdict(lambda: defaultdict(float))
    
    for profile in df['profile'].unique():
        profile_data = df[df['profile'] == profile]
        for bucket in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]:
            bucket_data = profile_data[profile_data['rank_bucket'] == bucket]
            if not bucket_data.empty:
                avg_matches = bucket_data['filter_matches'].mean()
                results[profile][bucket] = avg_matches
    
    return results

def plot_filter_matches(results):
    """Create line plot showing average filter matches across rank buckets."""
    plt.figure(figsize=(10, 6))
    
    # Define custom x-axis positions
    x_positions = [0, 0.4, 0.8, 1.5, 2.3, 3.0]
    
    # Plot for each profile
    for profile in results:
        style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})
        data = results[profile]
        x = []
        y = []
        
        for bucket in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]:
            if bucket in data:
                pos_idx = [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS].index(bucket)
                x.append(x_positions[pos_idx])
                y.append(data[bucket])
        
        plt.plot(x, y, 
                marker=style['marker'],
                color=style['color'],
                label=DISPLAY_NAMES.get(profile, profile),
                markersize=8,
                alpha=0.5,
                markeredgecolor='black',
                markeredgewidth=1.0,
                linewidth=1.5)
    
    plt.xlabel('')
    plt.ylabel('Average number of filter matches')
    plt.grid(True, alpha=0.3)
    
    # Set custom x-ticks
    plt.xticks(x_positions, 
               [rb.replace('Top ', '') for rb in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]], 
               rotation=45)
    
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout(rect=[0, 0, 0.85, 0.95])
    
    plt.savefig('analysis/graphs/filter_matches_by_rank.png', 
                dpi=300, 
                bbox_inches='tight',
                pad_inches=0.1)
    plt.close()

def main():
    results = analyze_filter_matches()
    plot_filter_matches(results)
    
    # Print average values
    print("\nAverage filter matches by rank bucket:")
    for bucket in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]:
        print(f"\nRank bucket: {bucket}")
        for profile in results:
            if bucket in results[profile]:
                print(f"  {DISPLAY_NAMES.get(profile, profile)}: {results[profile][bucket]:.1f}")

if __name__ == "__main__":
    main() 