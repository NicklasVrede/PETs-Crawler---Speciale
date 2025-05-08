import os
import json
import shutil
from pathlib import Path
from tqdm import tqdm

def is_failed_crawl(json_data):
    """
    Check if a crawl file shows signs of connection failures.
    Returns True if the file indicates a failed crawl.
    """
    # Check for visited_urls with errors
    if "visited_urls" in json_data.get("network_data", {}).get("0", {}):
        visited_urls = json_data["network_data"]["0"]["visited_urls"]
        
        # If all visited URLs have errors, it's a failed crawl
        if all("error" in url_data for url_data in visited_urls):
            # Check if errors are connection-related
            connection_errors = [
                "ERR_INTERNET_DISCONNECTED" in url_data.get("error", "")
                for url_data in visited_urls if "error" in url_data
            ]
            if connection_errors and all(connection_errors):
                return True
    
    return False

def cleanup_crawler_files(base_dir, action="move", failed_dir=None, dry_run=True):
    """
    Process crawler data files and handle failed crawls.
    
    Args:
        base_dir: Base directory containing profile subdirectories with JSON files
        action: Action to take - "move", "delete", or "report"
        failed_dir: Directory to move failed files to if action is "move"
        dry_run: If True, don't actually delete/move files, just report
    """
    if action == "move" and not failed_dir and not dry_run:
        raise ValueError("Failed directory must be specified when action is 'move'")
    
    if failed_dir:
        os.makedirs(failed_dir, exist_ok=True)
    
    stats = {"total": 0, "failed": 0, "processed": 0}
    failed_files = []
    
    # Get all profile directories
    profile_dirs = [d for d in os.listdir(base_dir) 
                   if os.path.isdir(os.path.join(base_dir, d))]
    
    for profile in tqdm(profile_dirs, desc="Processing profiles"):
        profile_dir = os.path.join(base_dir, profile)
        json_files = [f for f in os.listdir(profile_dir) 
                     if f.endswith('.json')]
        
        for json_file in tqdm(json_files, desc=f"Checking {profile}", leave=False):
            file_path = os.path.join(profile_dir, json_file)
            stats["total"] += 1
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if is_failed_crawl(data):
                    stats["failed"] += 1
                    failed_files.append(file_path)
                    
                    if not dry_run:
                        if action == "delete":
                            os.remove(file_path)
                            stats["processed"] += 1
                        elif action == "move":
                            dest_profile_dir = os.path.join(failed_dir, profile)
                            os.makedirs(dest_profile_dir, exist_ok=True)
                            shutil.move(file_path, os.path.join(dest_profile_dir, json_file))
                            stats["processed"] += 1
            except json.JSONDecodeError:
                print(f"Error parsing JSON file: {file_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
    
    return stats, failed_files

if __name__ == "__main__":
    # Configuration - Edit these values as needed
    BASE_DIR = "data/crawler_data"
    ACTION = "delete"  # Choose from: "report", "move", "delete"
    FAILED_DIR = "data/crawler_data_failed"
    DRY_RUN = False  # Set to False to actually perform the action
    
    print(f"Scanning directory: {BASE_DIR}")
    print(f"Action: {ACTION}" + (" (DRY RUN)" if DRY_RUN else ""))
    
    stats, failed_files = cleanup_crawler_files(
        BASE_DIR, 
        action=ACTION,
        failed_dir=FAILED_DIR,
        dry_run=DRY_RUN
    )
    
    print("\nResults:")
    print(f"Total files examined: {stats['total']}")
    print(f"Failed crawls identified: {stats['failed']}")
    
    if ACTION != "report" and not DRY_RUN:
        print(f"Files {ACTION}d: {stats['processed']}")
    
    if DRY_RUN and len(failed_files) > 0:
        print("\nFirst 10 failed files that would be processed:")
        for file in failed_files[:10]:
            print(f"  - {file}")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more") 