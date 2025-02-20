import sqlite3
from datetime import datetime
from typing import Dict, List

class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.setup_tables()

    def setup_tables(self):
        cursor = self.conn.cursor()
        
        # Sites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY,
                domain TEXT NOT NULL,
                visit_timestamp DATETIME NOT NULL
            )
        """)
        
        # Pages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                site_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                visit_timestamp DATETIME NOT NULL,
                FOREIGN KEY (site_id) REFERENCES sites (id)
            )
        """)
        
        # Network requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY,
                site_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                headers TEXT,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (site_id) REFERENCES sites (id)
            )
        """)
        
        # Cookies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cookies (
                id INTEGER PRIMARY KEY,
                site_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                value TEXT,
                domain TEXT,
                path TEXT,
                expires DATETIME,
                http_only BOOLEAN,
                secure BOOLEAN,
                same_site TEXT,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (site_id) REFERENCES sites (id)
            )
        """)
        
        self.conn.commit()

    def add_site(self, domain):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO sites (domain, visit_timestamp) VALUES (?, ?)",
            (domain, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_page(self, site_id, url):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO pages (site_id, url, visit_timestamp) VALUES (?, ?, ?)",
            (site_id, url, datetime.now())
        )
        self.conn.commit()

    def store_network_data(self, site_id: int, monitor: 'NetworkMonitor'):
        """Store network requests and cookies"""
        cursor = self.conn.cursor()
        
        # Store requests
        for req in monitor.requests:
            cursor.execute("""
                INSERT INTO requests (
                    site_id, url, method, resource_type, 
                    headers, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                site_id, req['url'], req['method'],
                req['resource_type'], str(req['headers']),
                req['timestamp']
            ))
        
        # Store cookies
        for cookie in monitor.cookies:
            cursor.execute("""
                INSERT INTO cookies (
                    site_id, name, value, domain, path,
                    expires, http_only, secure, same_site,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                site_id, cookie['name'], cookie['value'],
                cookie['domain'], cookie['path'], cookie['expires'],
                cookie['httpOnly'], cookie['secure'],
                cookie['sameSite'], cookie['timestamp']
            ))
        
        self.conn.commit() 