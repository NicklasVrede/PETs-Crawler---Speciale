import os
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

def analyze_cname_cloaking_for_profile(profile):
    """Analyze CNAME cloaking in JSON files for a specific profile."""
    json_dir = os.path.join("data/crawler_data", profile)
    if not os.path.exists(json_dir):
        print(f"Warning: Directory not found for profile {profile}")
        return 0
    
    cloaking_count = 0
    
    # Find all JSON files
    json_files = []
    for root, _, files in os.walk(json_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    # Process each JSON file
    for json_file in tqdm(json_files, desc=f"Analyzing {profile}", leave=False):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
                # Check domain_analysis section
                if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                    for domain_entry in data['domain_analysis']['domains']:
                        if domain_entry.get('cname_cloaking', False):
                            cloaking_count += 1
                            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    return cloaking_count

def plot_cloaking_by_profile(profile_counts):
    """Create a vertical bar plot of CNAME cloaking counts by profile with groupings."""
    # Order profiles according to groups
    ordered_profiles = []
    for group_profiles in PROFILE_GROUPS.values():
        ordered_profiles.extend([p for p in group_profiles if p in profile_counts])
    
    # Get counts in the correct order
    counts = [profile_counts[profile] for profile in ordered_profiles]
    display_names = [DISPLAY_NAMES.get(p, p) for p in ordered_profiles]
    
    # Create vertical bar plot
    fig, ax = plt.subplots(figsize=(14, 6))
    x_pos = range(len(ordered_profiles))
    ax.bar(x_pos, counts, color='lightblue', width=0.6)
    
    # Add group labels and separators
    current_position = 0
    y_max = max(counts) * 1.1  # Add 10% padding for group labels
    
    for group_name, group_profiles in PROFILE_GROUPS.items():
        group_profiles_in_data = [p for p in group_profiles if p in profile_counts]
        if group_profiles_in_data:
            group_start = current_position
            group_end = current_position + len(group_profiles_in_data) - 1
            
            # Add group label
            label_position = (group_start + group_end) / 2
            plt.text(label_position, y_max * 0.98, group_name,
                    ha='center', va='bottom', fontsize=12,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
            
            # Add separator line
            if current_position > 0:
                plt.axvline(x=current_position - 0.5,
                          color='black', linestyle=':', alpha=0.7)
            
            current_position += len(group_profiles_in_data)
    
    # Customize the plot
    plt.xticks(x_pos, display_names, rotation=45, ha='right')
    plt.ylabel('# of cloaked trackers')
    plt.title('CNAME Cloaking Instances by Profile')
    
    # Add value labels on top of the bars
    for i, v in enumerate(counts):
        plt.text(i, v, str(v), ha='center', va='bottom')
    
    # Add gridlines
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Create the graphs directory if it doesn't exist
    os.makedirs("analysis/graphs", exist_ok=True)
    
    # Save figure in the graphs directory
    plt.savefig('analysis/graphs/cname_cloaking_by_profile.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    # Get all profile directories
    crawler_data_dir = "data/crawler_data"
    profiles = [d for d in os.listdir(crawler_data_dir) 
               if os.path.isdir(os.path.join(crawler_data_dir, d))]
    
    print(f"Found {len(profiles)} profiles to analyze")
    
    # Analyze each profile
    profile_counts = {}
    for profile in profiles:
        count = analyze_cname_cloaking_for_profile(profile)
        if count > 0:  # Only include profiles with cloaking instances
            profile_counts[profile] = count
    
    # Print results
    print("\nCNAME Cloaking Analysis Results:")
    print("=" * 50)
    total_instances = sum(profile_counts.values())
    print(f"\nTotal CNAME cloaking instances across all profiles: {total_instances}")
    print("\nBreakdown by profile:")
    for profile, count in sorted(profile_counts.items(), key=lambda x: x[1], reverse=True):
        display_name = DISPLAY_NAMES.get(profile, profile)
        print(f"{display_name}: {count} instances")
    
    # Create visualization
    if profile_counts:
        plot_cloaking_by_profile(profile_counts)
    else:
        print("No CNAME cloaking found in any profile.")

if __name__ == "__main__":
    main() 