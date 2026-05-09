#!/usr/bin/env python3
"""
MySQL Reset Script with Safe Mode Handling
Run this from Python to avoid safe mode issues
"""

import sys
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'Sachhu55@#'),
    'database': os.getenv('DB_NAME', 'phantombox_db')
}

def reset_database():
    """Reset all tables using Python (bypasses safe mode)"""
    
    print("="*60)
    print("🗄️  PhantomBox MySQL Reset (Safe Mode Compatible)")
    print("="*60)
    
    conn = None
    cursor = None
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("\n🔓 Disabling foreign key checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Clear tables
        tables = ['shared_links', 'file_registry', 'user_sessions', 'audit_ledger']
        
        for table in tables:
            print(f"🗑️  Clearing {table}...")
            cursor.execute(f"DELETE FROM {table} WHERE 1=1")
            deleted = cursor.rowcount
            print(f"   Deleted {deleted} rows")
        
        # Clear test users (keep admins)
        print(f"🗑️  Clearing test users (keeping admins)...")
        cursor.execute("DELETE FROM users WHERE role != 'Admin' AND id IS NOT NULL")
        deleted = cursor.rowcount
        print(f"   Deleted {deleted} test users")
        
        print("\n🔒 Re-enabling foreign key checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        
        # Show summary
        print("\n" + "="*60)
        print("📊 Database Summary:")
        print("="*60)
        
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        print(f"   Users: {users}")
        
        cursor.execute("SELECT COUNT(*) FROM file_registry")
        files = cursor.fetchone()[0]
        print(f"   File registry: {files}")
        
        cursor.execute("SELECT COUNT(*) FROM audit_ledger")
        audit = cursor.fetchone()[0]
        print(f"   Audit logs: {audit}")
        
        cursor.execute("SELECT COUNT(*) FROM shared_links")
        shares = cursor.fetchone()[0]
        print(f"   Share links: {shares}")
        
        # Check if admin exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            print("\n👑 No admin found. Creating default admin...")
            import bcrypt
            
            admin_id = 'admin_001'
            email = 'admin@phantombox.local'
            password = 'Admin@2024'
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            
            cursor.execute("""
                INSERT INTO users (id, email, password_hash, first_name, last_name, role, is_active)
                VALUES (%s, %s, %s, %s, %s, 'Admin', 1)
            """, (admin_id, email, password_hash, 'System', 'Administrator'))
            conn.commit()
            
            print(f"   ✅ Created admin user:")
            print(f"      Email: {email}")
            print(f"      Password: {password}")
        
        print("\n" + "="*60)
        print("✅ Database reset complete!")
        print("="*60)
        
        return True
        
    except Error as e:
        print(f"\n❌ Database error: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_backup():
    """Create a backup before resetting"""
    import datetime
    import subprocess
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_phantombox_{timestamp}.sql"
    
    try:
        print(f"\n💾 Creating backup to {backup_file}...")
        
        # Use mysqldump command
        cmd = [
            'mysqldump',
            f"--host={DB_CONFIG['host']}",
            f"--port={DB_CONFIG['port']}",
            f"--user={DB_CONFIG['user']}",
            f"--password={DB_CONFIG['password']}",
            DB_CONFIG['database'],
            '--no-tablespaces'
        ]
        
        with open(backup_file, 'w') as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
        
        print(f"   ✅ Backup saved: {backup_file}")
        return backup_file
        
    except Exception as e:
        print(f"   ⚠️  Could not create backup: {e}")
        return None

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will DELETE ALL TEST DATA!")
    print("   - All files will be removed")
    print("   - All audit logs will be cleared")
    print("   - Test users will be deleted")
    print("   - Admin users will be preserved")
    print()
    
    backup = input("Create backup before reset? (Y/n): ").lower()
    if backup != 'n':
        create_backup()
    
    confirm = input("\nType 'RESET' to confirm: ")
    
    if confirm.upper() == 'RESET':
        reset_database()
    else:
        print("\n❌ Cancelled.")