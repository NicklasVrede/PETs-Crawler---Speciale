import os
import json
from datetime import datetime
from tqdm import tqdm
from managers.cookie_manager import analyze_cookie, cookie_db
from collections import Counter
import sys

def classify_site_cookies(data_dir):
    """Classify cookies in site data and add analysis to JSON files"""
    # Add debug print at the start
    tqdm.write("\nDebug: First 5 entries in cookie database:")
    for entry in list(cookie_db)[:5]:
        tqdm.write(str(entry))
    
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    for filename in tqdm(json_files, desc="Analyzing site cookies", unit="site"):
        file_path = os.path.join(data_dir, filename)
        
        try:
            # Load site data
            with open(file_path, 'r', encoding='utf-8') as f:
                site_data = json.load(f)
            
            # Get main site domain
            main_site = site_data.get('domain', filename.replace('.json', ''))
            
            # Initialize cookie statistics
            stats = {
                'total_cookies': 0,
                'identified_cookies': 0,
                'categories': Counter(),
                'providers': Counter(),
                'wildcard_matches': 0,
                'retention_known': 0,
                'cookies': []  # Will store detailed info about each cookie
            }
            
            # Extract all cookies from the site data
            all_cookies = []
            if 'cookies' in site_data:
                # Flatten cookies from all visits
                for visit_cookies in site_data['cookies'].values():
                    all_cookies.extend(visit_cookies)
            
            stats['total_cookies'] = len(all_cookies)
            
            # Create a set to track unique cookies by name+domain
            unique_cookies = set()
            
            # Analyze each cookie
            for cookie in all_cookies:
                cookie_name = cookie.get('name', '')
                cookie_domain = cookie.get('domain', '')
                
                # Normalize the domain by removing leading dot and www
                if cookie_domain:
                    cookie_domain = cookie_domain.lstrip('.')
                    if cookie_domain.startswith('www.'):
                        cookie_domain = cookie_domain[4:]
                
                # Skip if we've already analyzed this cookie
                cookie_key = f"{cookie_name}:{cookie_domain}"
                if cookie_key in unique_cookies:
                    continue
                unique_cookies.add(cookie_key)
                
                # Get cookie analysis
                analysis = analyze_cookie(cookie_name)
                
                if analysis:
                    stats['identified_cookies'] += 1
                    stats['categories'][analysis.get('category', 'unknown')] += 1
                    
                    # Use the normalized domain as the provider
                    provider = cookie_domain if cookie_domain else 'unknown'
                    stats['providers'][provider] += 1
                    
                    # Store detailed cookie info
                    cookie_info = {
                        'name': cookie_name,
                        'domain': cookie_domain,
                        'category': analysis.get('category', 'unknown'),
                        'provider': provider,
                        'description': analysis.get('description', ''),
                        'is_wildcard_match': analysis.get('is_wildcard', False)
                    }
                    stats['cookies'].append(cookie_info)
                else:
                    # Store unidentified cookie
                    cookie_info = {
                        'name': cookie_name,
                        'domain': cookie_domain,
                        'category': 'unknown',
                        'provider': cookie_domain if cookie_domain else 'unknown',
                        'description': 'Cookie not found in database',
                        'is_wildcard_match': False
                    }
                    stats['cookies'].append(cookie_info)
            
            # Convert counters to regular dictionaries for JSON serialization
            stats['categories'] = dict(stats['categories'])
            stats['providers'] = dict(stats['providers'])
            
            # Add analysis timestamp
            stats['analyzed_at'] = datetime.now().isoformat()
            
            # Add cookie analysis to site data
            site_data['cookie_analysis'] = stats
            
            # Save updated data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(site_data, f, indent=2)
            
            # Print summary
            tqdm.write(f"\nCookie analysis for {main_site}:")
            tqdm.write(f"Total cookies: {stats['total_cookies']}")
            
            # Fix the percentage calculation
            percentage = (stats['identified_cookies']/stats['total_cookies']*100) if stats['total_cookies'] > 0 else 0
            tqdm.write(f"Identified cookies: {stats['identified_cookies']} ({percentage:.1f}%)")
            tqdm.write(f"Wildcard matches: {stats['wildcard_matches']}")
            
            if stats['categories']:
                tqdm.write("\nTop cookie categories:")
                for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    percentage = (count/stats['total_cookies']*100) if stats['total_cookies'] > 0 else 0
                    tqdm.write(f"  - {category}: {count} ({percentage:.1f}%)")
            
            if stats['providers']:
                tqdm.write("\nTop cookie providers:")
                for provider, count in sorted(stats['providers'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    percentage = (count/stats['total_cookies']*100) if stats['total_cookies'] > 0 else 0
                    tqdm.write(f"  - {provider}: {count} ({percentage:.1f}%)")
                    
            # Add debug print for each cookie analysis
            for cookie in all_cookies:
                cookie_name = cookie.get('name', '')
                cookie_domain = cookie.get('domain', '')
                analysis = analyze_cookie(cookie_name)
                tqdm.write(f"\nAnalyzing cookie: {cookie_name} on {cookie_domain}")
                tqdm.write(f"Analysis result: {analysis}")
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")
            import traceback
            tqdm.write(traceback.format_exc())

if __name__ == "__main__":
    data_directory = 'data/crawler_data/i_dont_care_about_cookies'
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        tqdm.write(f"Error: Directory not found: {data_directory}")
        tqdm.write("Please ensure the data directory exists before running the script.")
        sys.exit(1)
    
    classify_site_cookies(data_directory)