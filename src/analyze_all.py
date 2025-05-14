import os
from tqdm import tqdm
from analyzers.source_identifier import SourceIdentifier
from analyzers.cookie_classifier import CookieClassifier
from analyzers.add_domain_categories import add_categories_to_files
from analyzers.banner_analyzer import BannerAnalyzer
from src.analyzers.storage_analyzer import StorageAnalyzer
import time
import subprocess
import sys
import concurrent.futures

# Fix subprocess encoding for Windows
if sys.platform == 'win32':
    # Store the original Popen
    original_popen = subprocess.Popen
    
    # Create a patched version that forces UTF-8
    def patched_popen(*args, **kwargs):
        if 'stdout' in kwargs and kwargs['stdout'] == subprocess.PIPE:
            kwargs['text'] = True
            kwargs['encoding'] = 'utf-8'
            kwargs['errors'] = 'replace'
        
        if 'stderr' in kwargs and kwargs['stderr'] == subprocess.PIPE:
            kwargs['text'] = True
            kwargs['encoding'] = 'utf-8'
            kwargs['errors'] = 'replace'
            
        return original_popen(*args, **kwargs)
    
    # Replace the original Popen with our patched version
    subprocess.Popen = patched_popen


# Helper function for parallel processing in Phase 3
def worker_process_folder_analyses(folder_path_tuple):
    folder_path, base_dir, banner_data_dir = folder_path_tuple
    # Create fresh instances for process safety.

    # CookieClassifier for the second pass (DB should be updated by Phase 2)
    # lookup_unknown=False is crucial here.
    cookie_classifier_worker = CookieClassifier(verbose=False)
    tqdm.write(f"Running final cookie classification for {os.path.basename(folder_path)}...")
    cookie_classifier_worker.classify_directory(folder_path, lookup_unknown=False)
    if cookie_classifier_worker.crawler: # Close crawler if it was somehow initialized
        cookie_classifier_worker.close()

    # Add domain categories
    tqdm.write(f"Adding domain categories for {os.path.basename(folder_path)}...")
    add_categories_to_files(folder_path)

    # Storage Analyzer
    storage_analyzer_worker = StorageAnalyzer(verbose=False)
    tqdm.write(f"Running storage analysis for {os.path.basename(folder_path)}...")
    storage_analyzer_worker.analyze_directory(folder_path)
    
    return f"Completed final analyses for {os.path.basename(folder_path)}"


def process_all_crawler_data(base_dir=None, banner_data_dir=None, max_workers=None):
    """Process all folders in crawler_data using all analyzers"""

    start_time = time.time()
    if base_dir is None:
        tqdm.write("No base directory provided, quitting")
        return

    # Get all folders in crawler_data
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    
    if not folders:
        tqdm.write("No folders found in data/crawler_data")
        return
        
    tqdm.write(f"Found {len(folders)} folders to process")
    
    # --- Phase 1: Sequential Source Identification and Initial Cookie Scan ---
    tqdm.write("Phase 1: Running Source Identification and Initial Cookie Scan (Sequentially)")
    source_identifier = SourceIdentifier()
    # This cookie_classifier_main instance will aggregate all unknown cookies
    cookie_classifier_main = CookieClassifier(verbose=False) 

    with tqdm(total=len(folders), desc="Phase 1 Processing", unit="folder") as progress_bar_phase1:
        for folder in folders:
            folder_path = os.path.join(base_dir, folder)
            progress_bar_phase1.set_description(f"Phase 1: {folder[:10]}...")
            
            # Run source identification (sequentially due to its cache)
            # tqdm.write(f"Running source identification for {folder[:10]}...")
            source_identifier.identify_site_sources(folder_path)
            
            # Initial cookie classification pass to gather unknown cookies
            # This will use cookie_classifier_main and populate its .unknown_cookies
            # It will also save an initial classification to the JSON files.
            # tqdm.write(f"Running initial cookie classification for {folder[:10]} (gathering unknowns)...")
            cookie_classifier_main.classify_directory(folder_path, lookup_unknown=False)
            
            progress_bar_phase1.update(1)

    # --- Phase 2: Sequential Lookup of All Aggregated Unknown Cookies ---
    tqdm.write("\nPhase 2: Looking up all aggregated unknown cookies (Sequentially)")
    if cookie_classifier_main.unknown_cookies:
        tqdm.write(f"Found {len(cookie_classifier_main.unknown_cookies)} unique unknown cookies to lookup.")
        cookie_classifier_main._init_crawler() # Ensure crawler is ready for the main instance
        if cookie_classifier_main.crawler:
            cookie_classifier_main.crawler.lookup_cookies_batch(list(cookie_classifier_main.unknown_cookies))
        # The database (CookieManager) is now updated.
        # Close the main crawler instance as it's no longer needed for lookups.
        cookie_classifier_main.close()
    else:
        tqdm.write("No new unknown cookies found to lookup.")

    # --- Phase 3: Parallel Final Analyses (Cookie Re-classification, Categories, Storage) ---
    tqdm.write("\nPhase 3: Running Final Cookie Re-classification, Category Addition, and Storage Analysis (In Parallel)")
    
    tasks = [(os.path.join(base_dir, folder), base_dir, banner_data_dir) for folder in folders]

    actual_max_workers = max_workers if max_workers is not None else os.cpu_count()
    if actual_max_workers is None: # os.cpu_count() can return None
        actual_max_workers = 1 
    else:
        actual_max_workers = min(actual_max_workers, len(tasks)) # Don't use more workers than tasks
        if actual_max_workers == 0 and len(tasks) > 0: # Ensure at least one worker if there are tasks
             actual_max_workers = 1

    tqdm.write(f"Using up to {actual_max_workers} worker processes for Phase 3.")

    if actual_max_workers > 0 and len(tasks) > 0:
        with concurrent.futures.ProcessPoolExecutor(max_workers=actual_max_workers) as executor:
            future_to_folder_path = {executor.submit(worker_process_folder_analyses, task): task[0] for task in tasks}
            
            for future in tqdm(concurrent.futures.as_completed(future_to_folder_path), total=len(tasks), desc="Phase 3 Processing Folders"):
                folder_path_processed = future_to_folder_path[future]
                try:
                    result = future.result()
                    tqdm.write(result)
                except Exception as exc:
                    tqdm.write(f"Folder {os.path.basename(folder_path_processed)} generated an exception during Phase 3: {exc}")
                    import traceback
                    tqdm.write(traceback.format_exc())
    elif len(tasks) > 0 : # Run sequentially if actual_max_workers ended up being 0 but there are tasks
        tqdm.write("Running Phase 3 sequentially as max_workers is 0 or no CPUs detected.")
        for task in tqdm(tasks, desc="Phase 3 Processing Folders (Sequential)"):
            try:
                result = worker_process_folder_analyses(task)
                tqdm.write(result)
            except Exception as exc:
                tqdm.write(f"Folder {os.path.basename(task[0])} generated an exception during Phase 3: {exc}")
                import traceback
                tqdm.write(traceback.format_exc())
    else:
        tqdm.write("No tasks for Phase 3.")
        
    # Banner analysis runs after all per-folder processing is complete.
    # It has its own parallelism settings.
    def run_banner_analysis():
        # Run banner analysis as the final step (processes all folders at once)
        tqdm.write("Running banner analysis...")
        banner_analyzer = BannerAnalyzer(
            banner_data_dir=banner_data_dir,
            crawler_data_dir=base_dir
        )
        
        # Run the banner analysis
        banner_analyzer.analyze_all_banners(
            test_run=False,            
            test_domain=None,
            test_count=None,
            use_parallel=True,
            max_workers=None
        )
    #run_banner_analysis()

    elapsed_time = time.time() - start_time
    
    tqdm.write(f"All analyses completed! Time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    #Make sure to check directory paths
    # You can specify max_workers here, e.g., max_workers=4
    process_all_crawler_data(base_dir="data/crawler_data", 
                             banner_data_dir="data/banner_data",
                             max_workers=os.cpu_count()) 