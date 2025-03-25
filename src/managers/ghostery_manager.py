import json
import subprocess
import os
import pickle
from typing import Dict
from urllib.parse import urlparse
import threading
import atexit
from tqdm import tqdm

class GhosteryManager:
    """
    A class to manage interactions with the Ghostery tracker database.
    Maintains a single Node.js process for efficient lookups.
    """
    _instance: 'GhosteryManager' = None
    _lock = threading.Lock()
    
    # Constants
    CACHE_FILE = 'data/ghostery_cache.pickle'
    BRIDGE_FILE = os.path.join('src', 'managers', 'ghostery_bridge.js')
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GhosteryManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._process = None
        self._cache = {}
        self._initialized = True
        
        # Load cache
        self._load_cache()
        
        # Create the JS bridge file if it doesn't exist
        self._ensure_bridge_file_exists()
        
        # Start the process
        self._start_db()
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _ensure_bridge_file_exists(self):
        """Create the JavaScript bridge file if it doesn't exist"""
        os.makedirs(os.path.dirname(self.BRIDGE_FILE), exist_ok=True)
        
        if not os.path.exists(self.BRIDGE_FILE):
            with open(self.BRIDGE_FILE, 'w') as f:
                f.write("""
const { urlDb } = require('@ghostery/trackerdb');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.on('line', async (url) => {
  try {
    const result = await urlDb.analyzeUrl(url);
    console.log(JSON.stringify(result));
  } catch (error) {
    console.log('{}');
  }
});

console.error('Ghostery bridge ready');
""")
    
    def _start_db(self):
        """Start the Node.js process"""
        try:
            tqdm.write("Starting Ghostery bridge process...")
            self._process = subprocess.Popen(
                ['node', self.BRIDGE_FILE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            # Read the "ready" message from stderr
            ready_msg = self._process.stderr.readline().strip()
            if 'ready' not in ready_msg.lower():
                tqdm.write(f"Warning: Unexpected message from Ghostery bridge: {ready_msg}")
            else:
                tqdm.write("Ghostery bridge process started successfully")
        except Exception as e:
            tqdm.write(f"Error starting Ghostery bridge: {e}")
            self._process = None
    
    def _ensure_process_running(self):
        """Ensure the Node.js process is running, restart if needed"""
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                tqdm.write("Restarting Ghostery bridge process...")
                self._start_db()
    
    def _load_cache(self):
        """Load Ghostery results cache from file"""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'rb') as f:
                    self._cache.update(pickle.load(f))
                    tqdm.write(f"Loaded {len(self._cache)} Ghostery cache entries")
        except Exception as e:
            tqdm.write(f"Error loading Ghostery cache: {e}")
    
    def _save_cache(self):
        """Save Ghostery results cache to file"""
        try:
            if self._cache:
                os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
                with open(self.CACHE_FILE, 'wb') as f:
                    pickle.dump(self._cache, f)
                tqdm.write(f"Saved {len(self._cache)} Ghostery cache entries")
        except Exception as e:
            tqdm.write(f"Error saving Ghostery cache: {e}")
    
    def analyze_request(self, url: str) -> Dict:
        """
        Return the full output from the Ghostery database for a given URL.
        
        Args:
            url: The URL to analyze
            
        Returns:
            A dictionary containing Ghostery's analysis of the URL
        """
        try:
            # Extract just the scheme and hostname
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Check cache first
            if base_url in self._cache:
                return self._cache[base_url]
            
            # Use direct npx command instead of the bridge process
            result = subprocess.run(
                ['npx', '@ghostery/trackerdb', base_url],
                capture_output=True,
                text=True,
                check=False,
                shell=True
            )
            
            # Parse the JSON output
            if result.stdout and '{' in result.stdout:
                json_start = result.stdout.find('{')
                json_end = result.stdout.rfind('}') + 1
                json_str = result.stdout[json_start:json_end]
                
                data = json.loads(json_str)
                
                # Cache the result
                self._cache[base_url] = data
                return data
            
            # Cache empty results too to avoid re-checking
            self._cache[base_url] = {}
            return {}
            
        except Exception as e:
            tqdm.write(f"Error analyzing {url}: {e}")
            return {}
    
    def cleanup(self):
        """Clean up resources and save cache"""
        self._save_cache()
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except:
                pass
            self._process = None

# Create a global instance for backwards compatibility
_ghostery_manager = GhosteryManager()

# Function for backwards compatibility with existing code
def analyze_request(url: str) -> Dict:
    """
    Legacy function that calls the singleton GhosteryManager.
    Kept for backwards compatibility.
    """
    return _ghostery_manager.analyze_request(url)

# Example usage
if __name__ == "__main__":
    test_urls = [
        "https://unagi.amazon.co.uk",
        "https://www.google.com",
        "https://www.facebook.com"
    ]
    
    for url in test_urls:
        tqdm.write(f"\nAnalyzing: {url}")
        tqdm.write("-" * 50)
        result = analyze_request(url)
        if result:
            tqdm.write(json.dumps(result, indent=2))
        else:
            tqdm.write("No tracking information found")
        tqdm.write("-" * 50)
    