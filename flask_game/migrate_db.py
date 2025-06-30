#!/usr/bin/env python3
"""
Simple database migration script to add missing columns
Run this once if you're getting "no column named last_activity" errors
"""

import sqlite3
from datetime import datetime
import os

def migrate_database():
    """Add missing last_activity column to existing database"""
    db_path = 'instance/game.db'
    
    if not os.path.exists(db_path):
        print("No existing database found. Run the main app to create tables.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if last_activity column exists
        cursor.execute("PRAGMA table_info(game)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'last_activity' not in columns:
            print("Adding last_activity column to game table...")
            cursor.execute("""
                ALTER TABLE game 
                ADD COLUMN last_activity DATETIME
            """)
            
            # Update existing games with their created_at timestamp
            cursor.execute("""
                UPDATE game 
                SET last_activity = created_at
            """)
            
            conn.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ Database is already up to date!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database() 