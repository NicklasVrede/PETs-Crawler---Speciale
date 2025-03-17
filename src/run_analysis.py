#!/usr/bin/env python3
"""
Script to run all post-processing analysis scripts on crawled data
"""
import os
import sys
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Add project root to path if needed
sys.path.append('.')

# Import analysis functions
from src.analyzers.cookie_analyzer import analyze_site_cookies
from src.identify_sources import analyze_site_sources
from src.analyze_cache_data import analyze_site_storage

# Set your parameters here
PROFILE = None  # Set to a specific profile name or None for all profiles
MAX_WORKERS = 4  # Number of parallel threads
FORCE_REANALYSIS = False  # Set to True to force reanalysis of all files

def run_analysis_on_file(file_path, skip_completed=True):
    """Run all analysis steps on a single file"""
    filename = os.path.basename(file_path)
    file_path_str = str(file_path)
    
    try:
        # Load the file to check if analyses are already done
        with open(file_path, 'r', encoding='utf-8') as f:
            site_data = json.load(f)
        
        # Track which analyses need to be performed
        need_cookie_analysis = not skip_completed or 'cookie_analysis' not in site_data
        need_domain_analysis = not skip_completed or 'domain_analysis' not in site_data
        need_storage_analysis = not skip_completed or 'storage_analysis' not in site_data
        
        if not (need_cookie_analysis or need_domain_analysis or need_storage_analysis):
            return {
                'file': filename,
                'status': 'skipped',
                'message': 'All analyses already completed'
            }
        
        analyses_run = []
        
        # Run cookie analysis if needed
        if need_cookie_analysis:
            try:
                analyze_site_cookies(file_path_str)
                analyses_run.append('cookies')
            except Exception as e:
                return {
                    'file': filename,
                    'status': 'error',
                    'message': f'Cookie analysis failed: {str(e)}'
                }
        
        # Run domain source analysis if needed
        if need_domain_analysis:
            try:
                analyze_site_sources(file_path_str)
                analyses_run.append('domains')
            except Exception as e:
                return {
                    'file': filename,
                    'status': 'error',
                    'message': f'Domain analysis failed: {str(e)}'
                }
        
        # Run storage analysis if needed
        if need_storage_analysis:
            try:
                analyze_site_storage(file_path_str)
                analyses_run.append('storage')
            except Exception as e:
                return {
                    'file': filename,
                    'status': 'error',
                    'message': f'Storage analysis failed: {str(e)}'
                }
        
        return {
            'file': filename,
            'status': 'success',
            'analyses_run': analyses_run
        }
        
    except Exception as e:
        return {
            'file': filename,
            'status': 'error',
            'message': f'Failed to process file: {str(e)}'
        }

def find_data_files(data_dir, profile=None):
    """Find all JSON data files in the given directory, optionally filtering by profile"""
    data_path = Path(data_dir)
    
    # If profile is specified, look in that specific profile folder
    if profile:
        profile_path = data_path / profile
        if profile_path.exists():
            return [f for f in profile_path.glob('*.json') if f.is_file()]
        else:
            tqdm.write(f"Profile directory not found: {profile_path}")
            return []
    
    # Otherwise look through all subdirectories
    json_files = []
    for subdir in [d for d in data_path.iterdir() if d.is_dir()]:
        json_files.extend([f for f in subdir.glob('*.json') if f.is_file()])
    
    return json_files

def main():
    """Run post-processing on all data files"""
    data_dir = os.path.join('data', 'crawler_data')
    
    # Find all JSON files
    json_files = find_data_files(data_dir, PROFILE)
    tqdm.write(f"Found {len(json_files)} JSON files to process")
    
    if not json_files:
        tqdm.write("No files found to process.")
        return
    
    # Process files with a thread pool
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Use tqdm to show progress
        futures = [executor.submit(run_analysis_on_file, f, not FORCE_REANALYSIS) for f in json_files]
        
        for future in tqdm(futures, total=len(json_files), desc="Analyzing files", unit="file"):
            results.append(future.result())
    
    # Summarize results
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    
    tqdm.write("\n===== Analysis Summary =====")
    tqdm.write(f"Total files: {len(results)}")
    tqdm.write(f"Successfully analyzed: {success_count}")
    tqdm.write(f"Errors: {error_count}")
    tqdm.write(f"Skipped (already analyzed): {skipped_count}")
    
    # Print details about errors if any
    if error_count > 0:
        tqdm.write("\nErrors encountered:")
        for result in [r for r in results if r['status'] == 'error']:
            tqdm.write(f"  {result['file']}: {result['message']}")
    
    # Print which analyses were run
    if success_count > 0:
        analyses_counts = {'cookies': 0, 'domains': 0, 'storage': 0}
        for result in [r for r in results if r['status'] == 'success']:
            for analysis in result.get('analyses_run', []):
                analyses_counts[analysis] += 1
        
        tqdm.write("\nAnalyses performed:")
        for analysis, count in analyses_counts.items():
            if count > 0:
                tqdm.write(f"  {analysis}: {count} files")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed = time.time() - start_time
    tqdm.write(f"\nTotal execution time: {elapsed:.2f} seconds") 