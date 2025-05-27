import os
import json
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES

# Define shorter names for profiles
profile_shortcuts = {
    'Baseline Profile': 'Baseline',
    'AdblockPlus': 'ABPlus',
    'Privacy Badger': 'P.Badger',
    'uBlock Origin Lite': 'uBO Lite',
    'Accept All Cookies': 'AcceptAll',
    'Cookie Cutter': 'C.Cutter',
    'Consent-O-Matic (Opt-in)': 'COM (in)',
    'Consent-O-Matic (Opt-out)': 'COM (out)',
    'Ghostery (Never Consent)': 'Ghost. (nc)',
    'I Don\'t Care About Cookies': 'IDontCare',
    'Super Agent ("Opt-in")': 'S.Agent (in)',
    'Super Agent ("Opt-out")': 'S.Agent (out)',
    'Decentraleyes': 'Decentral.'
}

def get_cname_stats(profile, successful_domains):
    """Get CNAME cloaking statistics for a profile."""
    json_dir = os.path.join("data/crawler_data", profile)
    cloaked_domains = set()
    cloaked_requests = 0
    
    for domain in tqdm(successful_domains, 
                      desc=f"Processing {profile} JSONs", 
                      leave=False):
        json_path = os.path.join(json_dir, f"{domain}.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                        for domain_entry in data['domain_analysis']['domains']:
                            if domain_entry.get('cname_cloaking', False):
                                cloaked_domains.add(domain_entry.get('domain', ''))
                                cloaked_requests += domain_entry.get('request_count', 0)
            except Exception as e:
                print(f"Error processing {json_path}: {e}")
    
    return len(cloaked_domains), cloaked_requests

def create_storage_tracking_table():
    print("Loading CSV data...")
    # Read the CSV data
    df = pd.read_csv("data/csv/final_data2.csv")
    df_loaded = df[df['page_status'] == 'loaded']

    print("Finding successful domains...")
    # Get successful domains
    all_profiles = df_loaded['profile'].unique()
    successful_domains = set()
    for domain in tqdm(df_loaded['domain'].unique(), desc="Checking domains"):
        if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
               for profile in all_profiles):
            successful_domains.add(domain)

    # Initialize results dictionary
    results = defaultdict(dict)

    # Process each profile
    print("\nProcessing profiles...")
    for profile in tqdm(all_profiles, desc="Analyzing profiles"):
        # Get storage data from CSV
        profile_data = df_loaded[df_loaded['profile'] == profile]
        
        results[profile].update({
            'local_storage': profile_data['local_storage_count'].sum(),
            'session_storage': profile_data['session_storage_count'].sum(),
            'storage_identifiers': profile_data['local_storage_potential_identifiers'].sum(),
            'tracker_requests': profile_data['total_requests'].sum()
        })
        
        # Get CNAME data from JSONs
        cloaked_domains, cloaked_requests = get_cname_stats(profile, successful_domains)
        results[profile].update({
            'cloaked_domains': cloaked_domains,
            'cloaked_requests': cloaked_requests
        })

    print("\nGenerating LaTeX table...")
    # Create LaTeX table
    latex_table = """\\begin{table}[t]
\\caption{Overview of storage usage and tracking methods per profile.}
\\label{tab:storage-tracking}
\\footnotesize
\\begin{tabular}{lrrrrrr}
\\toprule
\\textbf{Profile} & \\shortstack{\\textbf{Local}\\\\\\textbf{Storage}} & \\shortstack{\\textbf{Session}\\\\\\textbf{Storage}} & \\shortstack{\\textbf{Storage}\\\\\\textbf{Ident.}} & \\shortstack{\\textbf{CNAME}\\\\\\textbf{Domains}} & \\shortstack{\\textbf{CNAME}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Tracker}\\\\\\textbf{Req.}} \\\\
\\midrule
"""

    # Add rows
    for profile in all_profiles:
        # Use profile_shortcuts instead of DISPLAY_NAMES
        display_name = profile_shortcuts.get(DISPLAY_NAMES.get(profile, profile), DISPLAY_NAMES.get(profile, profile))
        data = results[profile]
        latex_table += (f"{display_name} & {data['local_storage']:,} & "
                       f"{data['session_storage']:,} & {data['storage_identifiers']:,} & "
                       f"{data['cloaked_domains']:,} & {data['cloaked_requests']:,} & "
                       f"{data['tracker_requests']:,} \\\\\n")

    # Add footer
    latex_table += """\\bottomrule
\\end{tabular}
\\end{table}"""

    # Save to file
    with open('analysis/tables/storage_tracking_table.tex', 'w') as f:
        f.write(latex_table)

    print("LaTeX table has been generated and saved to 'analysis/tables/storage_tracking_table.tex'")

if __name__ == "__main__":
    create_storage_tracking_table() 