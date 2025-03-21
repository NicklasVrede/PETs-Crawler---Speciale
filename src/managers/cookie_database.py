import json
import os
import time
from typing import Dict, Optional, List, Any
from tqdm import tqdm

class CookieDatabase:
    """
    Manages the cookie database with persistent storage.
    Provides methods for retrieving, adding, and updating cookie information.
    """
    
    def __init__(self, db_file='data/cookie_database.json'):
        """Initialize the cookie database."""
        self.db_file = db_file
        self.cookies = {}
        self.load()
    
    def load(self) -> None:
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
        
    def add_batch(self, cookies: Dict[str, Dict[str, Any]]) -> None:
        """
        Add multiple cookies to the database.
        
        Args:
            cookies: Dictionary mapping cookie names to their data
        """
        self.cookies.update(cookies)
    
    def create_unknown_cookie(self, name: str) -> Dict[str, Any]:
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
    
    def get_cookies_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all cookies of a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of cookies in the category
        """
        return [cookie for cookie in self.cookies.values() 
                if cookie.get('category', '').lower() == category.lower()]
    
    def get_cookies_by_script(self, script: str) -> List[Dict[str, Any]]:
        """
        Get all cookies associated with a specific script.
        
        Args:
            script: Script to filter by
            
        Returns:
            List of cookies from the script
        """
        return [cookie for cookie in self.cookies.values() 
                if cookie.get('script', '').lower() == script.lower()]
    
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
    
    def is_unknown(self, name: str) -> bool:
        """
        Check if a cookie exists but is classified as unknown.
        
        Args:
            name: Cookie name
            
        Returns:
            True if cookie exists and is unknown, False otherwise
        """
        if not self.contains(name):
            return False
        return self.cookies[name].get('category', '').lower() == 'unknown'

# Example usage
if __name__ == "__main__":
    db = CookieDatabase()
    
    # Example: Print statistics
    stats = db.get_statistics()
    print(f"Database contains {stats['total_cookies']} cookies")
    
    for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
        print(f"Category {category}: {count} cookies") 