#!/usr/bin/env python3
"""
Deployment script for Windows
Deploys the guessing game to the remote server
"""

import os
import subprocess
import sys
from pathlib import Path

# Try to import dotenv, install if needed
try:
    from dotenv import load_dotenv
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

def main():
    print("Starting deployment...")
    
    current_dir = Path.cwd()
    
    # Load environment variables from flask_game/.env
    env_file = current_dir / "flask_game" / ".env"
    if not env_file.exists():
        print("❌ Error: .env file not found in flask_game directory!")
        sys.exit(1)
    
    load_dotenv(env_file)
    scp_ip = os.environ.get('scpIP')
    if not scp_ip:
        print("❌ Error: 'scpIP' variable not found in .env file!")
        sys.exit(1)
    
    ssh_host = scp_ip.split(':')[0] if ':' in scp_ip else scp_ip
    
    # Delete database file if it exists
    db_file = current_dir / "flask_game" / "instance" / "game.db"
    if db_file.exists():
        try:
            db_file.unlink()
            print("✅ Database deleted")
        except Exception as e:
            print(f"⚠️ Warning: Could not delete database: {e}")
    
    # Check if flask_game directory exists
    flask_game_dir = current_dir / "flask_game"
    if not flask_game_dir.exists():
        print("❌ Error: flask_game directory not found!")
        sys.exit(1)
    
    # Test SSH connection
    ssh_test_command = [
        "ssh",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        ssh_host,
        "echo 'test'"
    ]
    
    try:
        subprocess.run(ssh_test_command, check=True, capture_output=True, timeout=15)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("❌ Error: SSH connection failed")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: 'ssh' command not found")
        sys.exit(1)
    
    # Upload files
    print("Uploading...")
    scp_command = ["scp", "-r", "-q", "flask_game", scp_ip]
    
    try:
        subprocess.run(scp_command, check=True, capture_output=True, timeout=300)
        print("✅ Deployment complete")
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e.stderr.decode().strip()}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("❌ Upload timed out")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: 'scp' command not found")
        sys.exit(1)

if __name__ == "__main__":
    main() 