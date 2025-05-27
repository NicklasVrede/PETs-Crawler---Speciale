import pandas as pd

# Read the CSV file
df = pd.read_csv("analysis/data tabel generation/cookie_summary_table.csv")

# Drop the unwanted columns
columns_to_drop = ['Others/Unknown', 'LocalStorage', 'SessionStorage']
df = df.drop(columns=columns_to_drop)

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

# Create LaTeX table header
latex_table = """\\begin{table}[t]
\\caption{Overview of cookie counts and categories per profile.}
\\label{tab:cookie-summary}
\\footnotesize
\\begin{tabular}{lrrrrrrrrr}
\\toprule
\\textbf{Profile} & \\textbf{Total} & \\textbf{1st P.} & \\textbf{3rd P.} & \\textbf{Nec.} & \\textbf{Func.} & \\textbf{Perf.} & \\textbf{Adv.} & \\textbf{Ana.} & \\textbf{1P Track.} \\\\
\\midrule
"""

# Add rows
for _, row in df.iterrows():
    profile_name = profile_shortcuts.get(row['profile'], row['profile'])
    latex_table += f"{profile_name} & "
    latex_table += f"{row['Total']:,} & "
    latex_table += f"{row['1st P.']:,} & "
    latex_table += f"{row['3rd P.']:,} & "
    latex_table += f"{row['Nec.']:,} & "
    latex_table += f"{row['Func.']:,} & "
    latex_table += f"{row['Perf.']:,} & "
    latex_table += f"{row['Adv.']:,} & "
    latex_table += f"{row['Ana.']:,} & "
    latex_table += f"{row['1st P. Track.']:,} & "
    latex_table += " \\\\\n"

# Add footer
latex_table += """\\bottomrule
\\end{tabular}
\\end{table}"""

# Save to file
with open('analysis/tables/cookie_summary.tex', 'w') as f:
    f.write(latex_table)

print("LaTeX table has been generated and saved to 'analysis/tables/cookie_summary.tex'") 