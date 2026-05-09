#!/usr/bin/env python3
"""
Clear all test files from storage nodes
Run this before your presentation to start fresh
"""

import os
import shutil
import requests
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clear_local_storage_nodes():
    """Clear persistent storage from noise_node_A and noise_node_B"""
    nodes = ['noise_storage_A', 'noise_storage_B']
    
    for node_dir in nodes:
        if os.path.exists(node_dir):
            print(f"🗑️  Clearing {node_dir}/...")
            try:
                shutil.rmtree(node_dir)
                print(f"   ✅ Removed {node_dir}")
            except Exception as e:
                print(f"   ❌ Error removing {node_dir}: {e}")
            
            # Recreate empty directory
            os.makedirs(node_dir, exist_ok=True)
            print(f"   📁 Recreated {node_dir}")
        else:
            print(f"⚠️  {node_dir} not found, skipping")

def clear_remote_storage_nodes():
    """Clear remote storage nodes via API (if running)"""
    nodes = [
        ('Noise Node A', 'http://127.0.0.1:9001/clear_all'),
        ('Noise Node B', 'http://127.0.0.1:9002/clear_all')
    ]
    
    for name, url in nodes:
        try:
            response = requests.delete(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Cleared {name} via API")
            else:
                print(f"⚠️  {name} returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"⚠️  {name} not running (connection refused)")
        except Exception as e:
            print(f"⚠️  Could not clear {name}: {e}")

def list_remaining_fragments():
    """List any remaining fragments for verification"""
    nodes = ['noise_storage_A', 'noise_storage_B']
    
    print("\n📋 Verifying cleanup:")
    total_fragments = 0
    
    for node_dir in nodes:
        if os.path.exists(node_dir):
            files = list(Path(node_dir).rglob('*.bin'))
            meta = list(Path(node_dir).rglob('*.meta.json'))
            
            if files or meta:
                print(f"\n   {node_dir}:")
                for f in files[:5]:
                    print(f"      - {f.name} ({f.stat().st_size} bytes)")
                if len(files) > 5:
                    print(f"      ... and {len(files)-5} more")
                total_fragments += len(files)
            else:
                print(f"\n   {node_dir}: ✅ Empty")
    
    if total_fragments == 0:
        print("\n✨ All storage nodes are clean!")
    else:
        print(f"\n⚠️  Found {total_fragments} fragments remaining")
    
    return total_fragments

if __name__ == "__main__":
    print("="*60)
    print("🧹 PhantomBox Storage Node Cleaner")
    print("="*60)
    
    # Ask for confirmation
    response = input("\n⚠️  This will DELETE ALL TEST FILES from storage nodes.\n   Continue? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Cancelled.")
        sys.exit(0)
    
    print("\n🧹 Clearing storage nodes...\n")
    
    # Clear local storage
    clear_local_storage_nodes()
    
    # Try remote API (if nodes are running)
    clear_remote_storage_nodes()
    
    # Verify cleanup
    fragments_left = list_remaining_fragments()
    
    print("\n" + "="*60)
    if fragments_left == 0:
        print("✅ Storage nodes successfully cleared!")
    else:
        print(f"⚠️  {fragments_left} fragments still exist. Manual cleanup may be needed.")
    print("="*60)