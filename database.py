"""
Database module for storing and retrieving mortality data.
"""

import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Optional
from config import DATABASE_PATH


class MortalityDatabase:
    """Database handler for mortality data storage and retrieval."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        # Defer table initialization - only create tables when needed
        # This speeds up import time
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ensure database tables are initialized."""
        if not self._initialized:
            self.init_database()
            self._initialized = True
    
    def init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        # Create table for monthly mortality data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_mortality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                total_patients INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                mortality_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hospital_name, year, month)
            )
        """)
        
        # Create table for daily mortality data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_mortality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL,
                date DATE NOT NULL,
                total_patients INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                mortality_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hospital_name, date)
            )
        """)
        
        # Create table for statistics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hospital_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL UNIQUE,
                avg_mortality_rate REAL,
                std_deviation REAL,
                threshold_3sd REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hospital_year_month 
            ON monthly_mortality(hospital_name, year, month)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hospital_date 
            ON daily_mortality(hospital_name, date)
        """)
        
        # Create table for daily PBD (Patient Bed Days) data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_pbd (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL,
                date DATE NOT NULL,
                total_pbd INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hospital_name, date)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pbd_hospital_date 
            ON daily_pbd(hospital_name, date)
        """)
        
        conn.commit()
        conn.close()
    
    def insert_monthly_data(self, hospital_name: str, year: int, month: int, 
                           total_patients: int, deaths: int, mortality_rate: float):
        """Insert or update monthly mortality data."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO monthly_mortality 
            (hospital_name, year, month, total_patients, deaths, mortality_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (hospital_name, year, month, total_patients, deaths, mortality_rate))
        
        conn.commit()
        conn.close()
    
    def insert_daily_data(self, hospital_name: str, date_obj: date, 
                         total_patients: int, deaths: int, mortality_rate: float):
        """Insert or update daily mortality data."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_mortality 
            (hospital_name, date, total_patients, deaths, mortality_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (hospital_name, date_obj.isoformat(), total_patients, deaths, mortality_rate))
        
        conn.commit()
        conn.close()
    
    def get_monthly_data(self, hospital_name: Optional[str] = None, 
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None) -> pd.DataFrame:
        """Retrieve monthly mortality data."""
        self._ensure_initialized()
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        
        query = "SELECT * FROM monthly_mortality WHERE 1=1"
        params = []
        
        if hospital_name:
            query += " AND hospital_name = ?"
            params.append(hospital_name)
        
        if start_date:
            query += " AND (year > ? OR (year = ? AND month >= ?))"
            params.extend([start_date.year, start_date.year, start_date.month])
        
        if end_date:
            query += " AND (year < ? OR (year = ? AND month <= ?))"
            params.extend([end_date.year, end_date.year, end_date.month])
        
        query += " ORDER BY hospital_name, year, month"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def get_all_hospitals(self) -> List[str]:
        """Get list of all unique hospital names."""
        self._ensure_initialized()
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT hospital_name FROM monthly_mortality ORDER BY hospital_name")
            hospitals = [row[0] for row in cursor.fetchall()]
            return hospitals
        finally:
            conn.close()
    
    def update_statistics(self, hospital_name: str, avg_mortality: float, 
                         std_deviation: float, threshold_3sd: float):
        """Update statistics for a hospital."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO hospital_statistics 
            (hospital_name, avg_mortality_rate, std_deviation, threshold_3sd, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (hospital_name, avg_mortality, std_deviation, threshold_3sd))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self, hospital_name: Optional[str] = None) -> pd.DataFrame:
        """Get statistics for hospitals."""
        self._ensure_initialized()
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        
        if hospital_name:
            df = pd.read_sql_query(
                "SELECT * FROM hospital_statistics WHERE hospital_name = ?",
                conn, params=[hospital_name]
            )
        else:
            df = pd.read_sql_query("SELECT * FROM hospital_statistics", conn)
        
        conn.close()
        return df
    
    def insert_daily_pbd(self, hospital_name: str, date_obj: date, total_pbd: int):
        """Insert or update daily PBD data."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_pbd 
            (hospital_name, date, total_pbd)
            VALUES (?, ?, ?)
        """, (hospital_name, date_obj.isoformat(), total_pbd))
        
        conn.commit()
        conn.close()
    
    def get_daily_pbd(self, hospital_name: Optional[str] = None,
                      start_date: Optional[date] = None,
                      end_date: Optional[date] = None) -> pd.DataFrame:
        """Retrieve daily PBD data."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        
        query = "SELECT date, hospital_name, total_pbd FROM daily_pbd WHERE 1=1"
        params = []
        
        if hospital_name:
            query += " AND hospital_name = ?"
            params.append(hospital_name)
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY hospital_name, date"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def get_raw_mortality_data(self, hospital_name: Optional[str] = None,
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> pd.DataFrame:
        """Get raw monthly mortality data for display."""
        self._ensure_initialized()
        return self.get_monthly_data(hospital_name, start_date, end_date)

