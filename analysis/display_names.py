# Display names mapping for profiles and extensions
DISPLAY_NAMES = {
    # Base profile
    "no_extensions": "Baseline Profile",
    
    # Ad blockers
    "adblock": "Adblock",
    "adblock_plus": "AdblockPlus",
    "disconnect": "Disconnect",
    "privacy_badger": "Privacy Badger",
    "ublock": "uBlock",
    "ublock_origin_lite": "uBlock Origin Lite",
    "adguard": "AdGuard",
    
    # Cookie/consent managers
    "accept_all_cookies": "Accept All Cookies",
    "cookie_cutter": "Cookie Cutter",
    "consent_o_matic_opt_in": "Consent-O-Matic (Opt-in)",
    "consent_o_matic_opt_out": "Consent-O-Matic (Opt-out)",
    "ghostery_tracker_&_ad_blocker": "Ghostery",
    "ghostery_tracker_&_ad_blocker_only_never_consent": "Ghostery (Never Consent)",
    "i_dont_care_about_cookies": "I Don't Care About Cookies",
    "super_agent": f'Super Agent ("Opt-out")', #"Legacy Suport"
    "super_agent_opt_in": f'Super Agent ("Opt-in")',
    "super_agent_opt_out": f'Super Agent ("Opt-out")',
    
    # Other
    "decentraleyes": "Decentraleyes"
}

# Profile grouping configuration
PROFILE_GROUPS = {
    "Baseline Profile": ["no_extensions"],
    
    "Traditional PETs": [
        "adblock", "adblock_plus", "disconnect", 
        "privacy_badger", "ublock", "ublock_origin_lite", "adguard"
    ],
    
    "Cookie Extensions": [
        "accept_all_cookies", "cookie_cutter", 
        "consent_o_matic_opt_in", "consent_o_matic_opt_out", 
        "ghostery_tracker_&_ad_blocker", "ghostery_tracker_&_ad_blocker_only_never_consent",
        "i_dont_care_about_cookies", 
        "super_agent", #"Legacy Suport"
        "super_agent_opt_in", 
        "super_agent_opt_out"
    ],
    
    "Other": ["decentraleyes"]
} 