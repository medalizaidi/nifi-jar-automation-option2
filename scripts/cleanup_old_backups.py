#!/usr/bin/env python3

import os
import sys
from datetime import datetime, timedelta
from github import Github

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'medalizaidi/nifi-jar-automation-option2')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')
RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', '15'))


def get_backup_folders(repo, backup_folder):
    """Get all backup date folders from GitHub"""
    try:
        contents = repo.get_contents(backup_folder, ref=BACKUP_BRANCH)
        # Filter for directories only (date folders like 2025-01-26)
        folders = [item for item in contents if item.type == "dir"]
        return folders
    except Exception as e:
        if "404" in str(e):
            print(f"  ℹ️  Backup folder '{backup_folder}' not found")
            return []
        raise e


def parse_date_folder(folder_name):
    """Parse date from folder name (YYYY-MM-DD format)"""
    try:
        return datetime.strptime(folder_name, '%Y-%m-%d')
    except ValueError:
        return None


def delete_folder_recursive(repo, path, branch):
    """Recursively delete a folder and all its contents"""
    try:
        contents = repo.get_contents(path, ref=branch)
        
        # If it's a single file
        if not isinstance(contents, list):
            contents = [contents]
        
        # Delete all files in the folder
        for content in contents:
            if content.type == "dir":
                # Recursively delete subdirectory
                delete_folder_recursive(repo, content.path, branch)
            else:
                # Delete file
                repo.delete_file(
                    content.path,
                    f"Cleanup: Remove old backup file {content.path}",
                    content.sha,
                    branch=branch
                )
                print(f"    ✅ Deleted file: {content.path}")
    except Exception as e:
        print(f"    ⚠️  Error deleting {path}: {e}")


def main():
    print("=" * 60)
    print("    NiFi Backup Cleanup Script")
    print("=" * 60)
    print("")
    
    # Validate required environment variables
    if not GITHUB_TOKEN:
        print("❌ Missing GITHUB_TOKEN environment variable")
        sys.exit(1)
    
    if not GITHUB_REPO:
        print("❌ Missing GITHUB_REPO environment variable")
        sys.exit(1)
    
    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    print(f"📅 Current Date: {datetime.utcnow().strftime('%Y-%m-%d')}")
    print(f"🗑️  Retention Period: {RETENTION_DAYS} days")
    print(f"📌 Cutoff Date: {cutoff_date.strftime('%Y-%m-%d')}")
    print(f"📦 GitHub Repo: {GITHUB_REPO}")
    print(f"📁 Backup Folder: {BACKUP_FOLDER}")
    print("")
    
    try:
        # Connect to GitHub
        print("Step 1: Connecting to GitHub...")
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        print("  ✅ Connected successfully")
        
        # Get all backup folders
        print("Step 2: Scanning backup folders...")
        backup_folders = get_backup_folders(repo, BACKUP_FOLDER)
        print(f"  ✅ Found {len(backup_folders)} date folders")
        
        if not backup_folders:
            print("")
            print("=" * 60)
            print("✅ NO BACKUPS TO CLEAN UP")
            print("=" * 60)
            return
        
        # Identify folders to delete
        print("Step 3: Identifying old backups...")
        folders_to_delete = []
        
        for folder in backup_folders:
            folder_date = parse_date_folder(folder.name)
            if folder_date and folder_date < cutoff_date:
                folders_to_delete.append((folder, folder_date))
        
        print(f"  ✅ Found {len(folders_to_delete)} folders to delete")
        
        if not folders_to_delete:
            print("")
            print("=" * 60)
            print("✅ NO OLD BACKUPS TO DELETE")
            print("   All backups are within retention period")
            print("=" * 60)
            return
        
        # Delete old folders
        print("Step 4: Deleting old backups...")
        deleted_count = 0
        
        for folder, folder_date in folders_to_delete:
            age_days = (datetime.utcnow() - folder_date).days
            print(f"  🗑️  Deleting: {folder.name} (age: {age_days} days)")
            delete_folder_recursive(repo, folder.path, BACKUP_BRANCH)
            deleted_count += 1
        
        print("")
        print("=" * 60)
        print("✅ CLEANUP COMPLETED SUCCESSFULLY")
        print(f"   📊 Deleted {deleted_count} backup folder(s)")
        print(f"   📁 Remaining backups are < {RETENTION_DAYS} days old")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()