import pandas as pd
import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Load the dataset
df = pd.read_csv("data/csv/final_data2.csv")

# Get all unique domains and profiles
all_domains = set(df['domain'].unique())
all_profiles = set(df['profile'].unique())

# For each domain, check which profiles didn't load
print("Domains with loading issues:")
print("============================")

for domain in all_domains:
    domain_data = df[df['domain'] == domain]
    
    # Check each profile's status for this domain
    failed_profiles = []
    missing_profiles = []
    
    for profile in all_profiles:
        profile_status = domain_data[domain_data['profile'] == profile]['page_status'].values
        
        if len(profile_status) == 0:
            missing_profiles.append(profile)
        elif profile_status[0] != 'loaded':
            failed_profiles.append(f"{profile} (status: {profile_status[0]})")
    
    # If there were any issues, print them
    if failed_profiles or missing_profiles:
        print(f"\nDomain: {domain}")
        if failed_profiles:
            print("Failed profiles:")
            for profile in failed_profiles:
                print(f"  - {profile}")
        if missing_profiles:
            print("Missing profiles:")
            for profile in missing_profiles:
                print(f"  - {profile}") 