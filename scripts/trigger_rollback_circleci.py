#!/usr/bin/env python3
"""
CircleCI Rollback Trigger Script
Triggers the rollback pipeline via CircleCI API with date/time parameters
Usage: python trigger_rollback_circleci.py [--list] [--date YYYY-MM-DD] [--time HH-MM-UTC]
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime


# Configuration
CIRCLECI_TOKEN = os.environ.get('CIRCLECI_TOKEN')
REPO_OWNER = os.environ.get('REPO_OWNER', 'medalizadi')
REPO_NAME = os.environ.get('REPO_NAME', 'nifi-jar-automation-option2')
BRANCH = os.environ.get('BRANCH', 'main')


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 70}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text:^70}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 70}{Colors.NC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.NC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.NC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.NC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.NC}")


def validate_token():
    """Validate CircleCI token is set"""
    if not CIRCLECI_TOKEN:
        print_error("CIRCLECI_TOKEN environment variable is not set")
        print()
        print("To set your token:")
        print("  export CIRCLECI_TOKEN='your_personal_api_token_here'")
        print()
        print("Get your token at:")
        print("  https://app.circleci.com/settings/user/tokens")
        return False
    return True


def validate_date_format(date_str):
    """Validate date is in YYYY-MM-DD format"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_time_format(time_str):
    """Validate time is in HH-MM-UTC format"""
    if not time_str.endswith('-UTC'):
        return False
    try:
        time_part = time_str.replace('-UTC', '')
        datetime.strptime(time_part, '%H-%M')
        return True
    except ValueError:
        return False


def trigger_circleci_pipeline(parameters=None):
    """
    Trigger CircleCI pipeline via API
    
    Args:
        parameters (dict): Pipeline parameters
    
    Returns:
        dict: API response or None if failed
    """
    url = f"https://circleci.com/api/v2/project/gh/{REPO_OWNER}/{REPO_NAME}/pipeline"
    
    headers = {
        "Content-Type": "application/json",
        "Circle-Token": CIRCLECI_TOKEN
    }
    
    payload = {
        "branch": BRANCH
    }
    
    if parameters:
        payload["parameters"] = parameters
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print_error(f"HTTP Error: {e}")
        if response.text:
            try:
                error_data = json.loads(response.text)
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Error response: {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return None


def get_pipeline_workflows(pipeline_id):
    """
    Get workflows for a pipeline
    
    Args:
        pipeline_id (str): Pipeline ID
        
    Returns:
        list: List of workflows
    """
    url = f"https://circleci.com/api/v2/pipeline/{pipeline_id}/workflow"
    
    headers = {
        "Circle-Token": CIRCLECI_TOKEN
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get('items', [])
    except:
        return []


def list_backups():
    """Trigger pipeline to list available backups"""
    print_header("List Available NiFi Backups")
    
    print_info("Triggering CircleCI pipeline without parameters...")
    print_info("This will show all available backups from GitHub")
    print()
    
    result = trigger_circleci_pipeline()
    
    if result:
        pipeline_id = result.get('id')
        pipeline_number = result.get('number')
        
        print_success("Pipeline triggered successfully!")
        print()
        print(f"{Colors.BOLD}Pipeline Details:{Colors.NC}")
        print(f"  📊 Number: {pipeline_number}")
        print(f"  🆔 ID: {pipeline_id}")
        print(f"  🌿 Branch: {BRANCH}")
        print()
        
        pipeline_url = f"https://app.circleci.com/pipelines/github/{REPO_OWNER}/{REPO_NAME}/{pipeline_number}"
        print(f"{Colors.BOLD}View Pipeline:{Colors.NC}")
        print(f"  {Colors.BLUE}{pipeline_url}{Colors.NC}")
        print()
        
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print(f"{Colors.CYAN}Next Steps:{Colors.NC}")
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print("1. Click the pipeline URL above")
        print("2. Wait for 'list-available-backups' job to complete")
        print("3. Click on the job to view logs")
        print("4. Note the backup date and time you want to restore")
        print()
        print("Then run:")
        print(f"  {Colors.YELLOW}python {sys.argv[0]} --date YYYY-MM-DD --time HH-MM-UTC{Colors.NC}")
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print()
        
        return True
    
    return False


def rollback_to_backup(backup_date, backup_time):
    """
    Trigger rollback to specific backup
    
    Args:
        backup_date (str): Backup date in YYYY-MM-DD format
        backup_time (str): Backup time in HH-MM-UTC format
    """
    print_header("NiFi Rollback Execution")
    
    # Validate date format
    if not validate_date_format(backup_date):
        print_error(f"Invalid date format: {backup_date}")
        print()
        print("Expected format: YYYY-MM-DD")
        print("Examples:")
        print("  ✅ 2026-01-26")
        print("  ✅ 2025-12-31")
        print("  ❌ 26-01-2026 (wrong order)")
        print("  ❌ 2026/01/26 (wrong separator)")
        return False
    
    # Validate time format
    if not validate_time_format(backup_time):
        print_error(f"Invalid time format: {backup_time}")
        print()
        print("Expected format: HH-MM-UTC")
        print("Examples:")
        print("  ✅ 12-00-UTC")
        print("  ✅ 00-00-UTC")
        print("  ✅ 23-59-UTC")
        print("  ❌ 12-00 (missing -UTC)")
        print("  ❌ 12:00-UTC (wrong separator)")
        return False
    
    # Show rollback details
    print(f"{Colors.MAGENTA}{Colors.BOLD}Rollback Configuration:{Colors.NC}")
    print(f"  📅 Backup Date: {Colors.BOLD}{backup_date}{Colors.NC}")
    print(f"  🕐 Backup Time: {Colors.BOLD}{backup_time}{Colors.NC}")
    print(f"  🔗 Repository: {REPO_OWNER}/{REPO_NAME}")
    print(f"  🌿 Branch: {BRANCH}")
    print()
    
    # Warning
    print_warning("This will initiate a ROLLBACK operation")
    print()
    print(f"{Colors.YELLOW}What will happen:{Colors.NC}")
    print("  1. Pipeline will be triggered with your parameters")
    print("  2. Parameters will be validated automatically")
    print("  3. You'll need to APPROVE the rollback in CircleCI UI")
    print("  4. Backup will be downloaded from GitHub")
    print("  5. Backup file will be saved to CircleCI artifacts")
    print("  6. You'll receive instructions to complete the rollback")
    print()
    
    # Confirmation
    try:
        confirm = input(f"{Colors.YELLOW}{Colors.BOLD}Are you sure you want to proceed? (yes/no): {Colors.NC}")
        if confirm.lower() != 'yes':
            print()
            print_warning("Rollback cancelled by user")
            return False
    except (KeyboardInterrupt, EOFError):
        print()
        print_warning("Rollback cancelled by user")
        return False
    
    print()
    print_info("Triggering CircleCI rollback pipeline...")
    print()
    
    # Trigger with parameters
    parameters = {
        "backup-date": backup_date,
        "backup-time": backup_time
    }
    
    result = trigger_circleci_pipeline(parameters)
    
    if result:
        pipeline_id = result.get('id')
        pipeline_number = result.get('number')
        
        print_success("Rollback pipeline triggered successfully!")
        print()
        print(f"{Colors.BOLD}Pipeline Details:{Colors.NC}")
        print(f"  📊 Number: {pipeline_number}")
        print(f"  🆔 ID: {pipeline_id}")
        print(f"  📅 Date: {backup_date}")
        print(f"  🕐 Time: {backup_time}")
        print()
        
        pipeline_url = f"https://app.circleci.com/pipelines/github/{REPO_OWNER}/{REPO_NAME}/{pipeline_number}"
        print(f"{Colors.BOLD}View Pipeline:{Colors.NC}")
        print(f"  {Colors.BLUE}{pipeline_url}{Colors.NC}")
        print()
        
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print(f"{Colors.CYAN}{Colors.BOLD}IMPORTANT - Action Required:{Colors.NC}")
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print()
        print(f"{Colors.BOLD}Step 1: Open Pipeline{Colors.NC}")
        print(f"  Click the URL above or go to CircleCI")
        print()
        print(f"{Colors.BOLD}Step 2: Wait for Validation{Colors.NC}")
        print(f"  The 'validate-parameters' job will run automatically")
        print(f"  ✅ If parameters are valid, it proceeds to approval")
        print(f"  ❌ If invalid, the pipeline stops with error message")
        print()
        print(f"{Colors.BOLD}Step 3: Approve the Rollback{Colors.NC}")
        print(f"  1. Find the 'execute-rollback' workflow")
        print(f"  2. Click on 'hold-for-rollback-approval' job")
        print(f"  3. Review the rollback details carefully")
        print(f"  4. Click the {Colors.GREEN}[Approve]{Colors.NC} button")
        print()
        print(f"{Colors.BOLD}Step 4: Monitor Execution{Colors.NC}")
        print(f"  1. Watch the 'nifi-rollback' job logs")
        print(f"  2. Backup will be downloaded from GitHub")
        print(f"  3. Go to 'Artifacts' tab when job completes")
        print(f"  4. Download the backup file")
        print()
        print(f"{Colors.BOLD}Step 5: Complete in NiFi UI{Colors.NC}")
        print(f"  Follow the instructions in the job logs to:")
        print(f"  - Stop processors in NiFi")
        print(f"  - Upload the backup file")
        print(f"  - Apply changes")
        print(f"  - Restart processors")
        print()
        print(f"{Colors.CYAN}{'─' * 70}{Colors.NC}")
        print()
        
        # Try to get workflow info
        print_info("Fetching workflow information...")
        workflows = get_pipeline_workflows(pipeline_id)
        if workflows:
            print()
            print(f"{Colors.BOLD}Workflow Status:{Colors.NC}")
            for workflow in workflows:
                name = workflow.get('name', 'Unknown')
                status = workflow.get('status', 'unknown')
                workflow_id = workflow.get('id', '')
                
                status_icon = {
                    'running': '🔄',
                    'success': '✅',
                    'failed': '❌',
                    'on_hold': '⏸️',
                    'canceled': '⛔',
                    'not_run': '⏭️'
                }.get(status, '❓')
                
                print(f"  {status_icon} {name}: {status}")
        
        print()
        return True
    
    return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Trigger NiFi rollback pipeline via CircleCI API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available backups
  python trigger_rollback_circleci.py --list
  
  # Rollback to specific backup
  python trigger_rollback_circleci.py --date 2026-01-26 --time 12-00-UTC
  
  # Using custom repository
  export REPO_OWNER="myorg"
  export REPO_NAME="my-nifi-repo"
  python trigger_rollback_circleci.py --date 2026-01-26 --time 12-00-UTC

Environment Variables:
  CIRCLECI_TOKEN  Your CircleCI personal API token (required)
  REPO_OWNER      GitHub repository owner (default: avaxops)
  REPO_NAME       GitHub repository name (default: nifi-jar-automation-option2)
  BRANCH          Branch to trigger (default: main)
        """
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available backups'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        metavar='YYYY-MM-DD',
        help='Backup date to restore (format: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--time',
        type=str,
        metavar='HH-MM-UTC',
        help='Backup time to restore (format: HH-MM-UTC)'
    )
    
    parser.add_argument(
        '--repo-owner',
        type=str,
        help='GitHub repository owner (overrides REPO_OWNER env var)'
    )
    
    parser.add_argument(
        '--repo-name',
        type=str,
        help='GitHub repository name (overrides REPO_NAME env var)'
    )
    
    parser.add_argument(
        '--branch',
        type=str,
        help='Branch name (overrides BRANCH env var)'
    )
    
    args = parser.parse_args()
    
    # Override globals if provided
    global REPO_OWNER, REPO_NAME, BRANCH
    if args.repo_owner:
        REPO_OWNER = args.repo_owner
    if args.repo_name:
        REPO_NAME = args.repo_name
    if args.branch:
        BRANCH = args.branch
    
    # Validate token
    if not validate_token():
        sys.exit(1)
    
    # Execute command
    success = False
    
    if args.list:
        success = list_backups()
    elif args.date and args.time:
        success = rollback_to_backup(args.date, args.time)
    elif args.date or args.time:
        print_error("Both --date and --time are required for rollback")
        print()
        print("Usage:")
        print("  python trigger_rollback_circleci.py --date YYYY-MM-DD --time HH-MM-UTC")
        print()
        print("Or to list available backups:")
        print("  python trigger_rollback_circleci.py --list")
        print()
        parser.print_help()
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()