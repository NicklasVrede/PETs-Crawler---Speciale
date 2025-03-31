import json
import os
import time
from typing import Dict, Optional, List, Any
from tqdm import tqdm

class CookieManager:
    """
    Manages the cookie database with persistent storage.
    Provides methods for retrieving, adding, and updating cookie information.
    """
    
    def __init__(self, db_file='data/db+ref/cookie_database.json'):
        """Initialize the cookie database."""
        self.db_file = db_file
        self.cookies = {}
        self._load()
    
    def _load(self) -> None:
        """Load the cookie database from file."""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    self.cookies = json.load(f)
                tqdm.write(f"Loaded {len(self.cookies)} cookie definitions from {self.db_file}")
            else:
                tqdm.write(f"Cookie database file not found at {self.db_file}. Starting with empty database.")
        except Exception as e:
            tqdm.write(f"Error loading cookie database: {str(e)}")
    
    def save(self) -> None:
        """Save the cookie database to file."""
        try:
            if self.cookies:
                os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
                with open(self.db_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cookies, f, indent=2)
                tqdm.write(f"Saved {len(self.cookies)} cookie definitions to {self.db_file}")
        except Exception as e:
            tqdm.write(f"Error saving cookie database: {str(e)}")
    
    def get(self, name: str, default=None) -> Optional[Dict[str, Any]]:
        """
        Get cookie information by name.
        
        Args:
            name: Cookie name
            default: Default value if cookie not found
            
        Returns:
            Cookie information or default value if not found
        """
        return self.cookies.get(name, default)
    
    def add(self, name: str, cookie_data: Dict[str, Any]) -> None:
        """
        Add or update a cookie in the database.
        
        Args:
            name: Cookie name
            cookie_data: Cookie information dictionary
        """
        self.cookies[name] = cookie_data
    
    def create_unknown(self, name: str) -> Dict[str, Any]:
        """
        Create a record for an unknown cookie.
        
        Args:
            name: Cookie name
            
        Returns:
            Cookie information for unknown cookie
        """
        return {
            'name': name,
            'cookie_id': 'Not specified',
            'category': 'Unknown',
            'script': 'Not specified',
            'description': 'No match found',
            'url': 'Not specified',
            'script_url': 'Not specified',
            'found_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'match_type': 'none'
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the cookie database.
        
        Returns:
            Dictionary with database statistics
        """
        categories = {}
        scripts = {}
        match_types = {}
        
        for cookie in self.cookies.values():
            category = cookie.get('category', 'Unknown')
            script = cookie.get('script', 'Not specified')
            match_type = cookie.get('match_type', 'none')
            
            categories[category] = categories.get(category, 0) + 1
            scripts[script] = scripts.get(script, 0) + 1
            match_types[match_type] = match_types.get(match_type, 0) + 1
        
        return {
            'total_cookies': len(self.cookies),
            'categories': categories,
            'scripts': scripts,
            'match_types': match_types
        }
    
    def contains(self, name: str) -> bool:
        """
        Check if a cookie exists in the database.
        
        Args:
            name: Cookie name
            
        Returns:
            True if cookie exists, False otherwise
        """
        return name in self.cookies


# Example usage
if __name__ == "__main__":
    db = CookieManager()
    
    # Example: Print statistics
    stats = db.get_statistics()
    print(f"Database contains {stats['total_cookies']} cookies")
    
    for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
        print(f"Category {category}: {count} cookies") 