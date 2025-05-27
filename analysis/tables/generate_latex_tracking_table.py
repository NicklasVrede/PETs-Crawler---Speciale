import os
import sys
import pandas as pd
from collections import defaultdict
from tqdm import tqdm

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

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

def create_tracking_table():
    print("Loading CSV data...")
    # Read the CSV data
    df = pd.read_csv("data/csv/final_data2.csv")
    df_loaded = df[df['page_status'] == 'loaded']

    # Define columns to sum
    tracking_cols = {
        'Advertising': 'advertising_requests',
        'Analytics': 'analytics_requests',
        'Social': 'social_media_requests',
        'Consent': 'consent_management_requests',
        'Hosting': 'hosting_requests',
        'Canvas': 'canvas_fingerprinting_calls',
        'Audio': 'media_fingerprinting_calls',
        'WebRTC': 'hardware_fingerprinting_calls',
        'WebGL': 'webgl_fingerprinting_calls'
    }

    # Initialize results dictionary
    results = defaultdict(dict)

    # Process each profile
    print("\nProcessing profiles...")
    for profile in tqdm(df_loaded['profile'].unique(), desc="Analyzing profiles"):
        profile_data = df_loaded[df_loaded['profile'] == profile]
        
        # Sum up each tracking category
        for category, col in tracking_cols.items():
            results[profile][category] = profile_data[col].sum()

    # Create LaTeX table
    latex_table = """\\begin{table}[t]
\\caption{Overview of tracking requests and fingerprinting calls per profile.}
\\label{tab:tracking-summary}
\\footnotesize
\\begin{tabular}{lrrrrrrrrr}
\\toprule
\\textbf{Profile} & \\shortstack{\\textbf{Advert.}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Analyt.}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Social}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Consent}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Hosting}\\\\\\textbf{Req.}} & \\shortstack{\\textbf{Canvas}\\\\\\textbf{Calls}} & \\shortstack{\\textbf{Audio}\\\\\\textbf{Calls}} & \\shortstack{\\textbf{WebRTC}\\\\\\textbf{Calls}} & \\shortstack{\\textbf{WebGL}\\\\\\textbf{Calls}} \\\\
\\midrule
"""

    # Add rows in the order defined by PROFILE_GROUPS
    for group, profiles in PROFILE_GROUPS.items():
        for profile_id in profiles:
            display_name = DISPLAY_NAMES[profile_id]
            # Use the shortened profile name
            short_name = profile_shortcuts.get(display_name, display_name)
            data = results[profile_id]
            latex_table += (f"{short_name} & "
                          f"{data['Advertising']:,} & "
                          f"{data['Analytics']:,} & "
                          f"{data['Social']:,} & "
                          f"{data['Consent']:,} & "
                          f"{data['Hosting']:,} & "
                          f"{data['Canvas']:,} & "
                          f"{data['Audio']:,} & "
                          f"{data['WebRTC']:,} & "
                          f"{data['WebGL']:,}"
                          " \\\\\n")

    # Add footer
    latex_table += """\\bottomrule
\\end{tabular}
\\end{table}"""

    # Save to file
    with open('analysis/tables/tracking_table.tex', 'w') as f:
        f.write(latex_table)

    print("LaTeX table has been generated and saved to 'analysis/tables/tracking_table.tex'")

if __name__ == "__main__":
    create_tracking_table() 