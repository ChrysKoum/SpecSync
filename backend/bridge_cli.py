"""
CLI interface for SpecSync Bridge.

Provides command-line interface for managing bridge operations:
- init: Initialize bridge configuration
- add-dependency: Add a new dependency
- sync: Sync contracts from dependencies
- validate: Validate API calls against contracts
- status: Show status of all dependencies
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from backend.bridge_models import (
    BridgeConfig,
    Dependency,
    load_config,
    load_contract_from_yaml
)
from backend.bridge_sync import SyncEngine
from backend.bridge_drift_detector import BridgeDriftDetector, format_drift_report


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal formatting."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'


class BridgeCLI:
    """Command-line interface for SpecSync Bridge."""
    
    def __init__(self, repo_root: str = "."):
        """
        Initialize CLI.
        
        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = Path(repo_root)
        self.config_path = self.repo_root / ".kiro/settings/bridge.json"
    
    def init(self, role: str = "consumer") -> None:
        """
        Initialize bridge configuration.
        
        Creates:
        - .kiro/settings/bridge.json configuration file
        - .kiro/contracts/ directory for contract storage
        
        Args:
            role: Role of this repository (consumer, provider, or both)
        """
        print(f"{Colors.BOLD}Initializing SpecSync Bridge...{Colors.RESET}\n")
        
        # Validate role
        if role not in ['consumer', 'provider', 'both']:
            print(f"{Colors.RED}✗ Invalid role: {role}{Colors.RESET}")
            print(f"  Valid roles: consumer, provider, both")
            sys.exit(1)
        
        # Check if already initialized
        if self.config_path.exists():
            print(f"{Colors.YELLOW}⚠  Bridge already initialized{Colors.RESET}")
            print(f"  Config file: {self.config_path}")
            
            response = input("\nOverwrite existing configuration? (y/N): ")
            if response.lower() != 'y':
                print("Initialization cancelled")
                return
        
        # Create configuration
        config = BridgeConfig.create_default(role=role, config_path=str(self.config_path))
        config.save()
        
        # Create contracts directory
        contracts_dir = self.repo_root / ".kiro/contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        
        # Create README in contracts directory
        readme_path = contracts_dir / "README.md"
        if not readme_path.exists():
            readme_content = """# Contract Cache

This directory stores cached API contracts from dependencies.

## Files

- `provided-api.yaml`: Contract provided by this repository (if provider)
- `<dependency>-api.yaml`: Cached contracts from dependencies
- `<dependency>-expectations.yaml`: Consumer expectations for each dependency

## Usage

Run `specsync bridge sync` to update cached contracts.
Run `specsync bridge validate` to check for drift.
"""
            readme_path.write_text(readme_content)
        
        print(f"{Colors.GREEN}✓ Bridge initialized successfully{Colors.RESET}\n")
        print(f"  Role: {Colors.BOLD}{role}{Colors.RESET}")
        print(f"  Config: {self.config_path}")
        print(f"  Contracts: {contracts_dir}")
        
        if role in ['provider', 'both']:
            print(f"\n{Colors.CYAN}Next steps for providers:{Colors.RESET}")
            print(f"  1. Extract your API contract:")
            print(f"     python -m backend.bridge_contract_extractor")
            print(f"  2. Commit the contract file to your repository")
        
        if role in ['consumer', 'both']:
            print(f"\n{Colors.CYAN}Next steps for consumers:{Colors.RESET}")
            print(f"  1. Add dependencies:")
            print(f"     specsync bridge add-dependency <name> --git-url <url>")
            print(f"  2. Sync contracts:")
            print(f"     specsync bridge sync")
            print(f"  3. Validate your code:")
            print(f"     specsync bridge validate")
    
    def add_dependency(self, name: str, git_url: str, contract_path: str = ".kiro/contracts/provided-api.yaml") -> None:
        """
        Add a new dependency to the configuration.
        
        Args:
            name: Name of the dependency
            git_url: Git repository URL
            contract_path: Path to contract file in the dependency repo
        """
        print(f"{Colors.BOLD}Adding dependency: {name}{Colors.RESET}\n")
        
        # Load existing configuration
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized{Colors.RESET}")
            print(f"  Run 'specsync bridge init' first")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        # Check if dependency already exists
        if config.get_dependency(name):
            print(f"{Colors.YELLOW}⚠  Dependency '{name}' already exists{Colors.RESET}")
            response = input("\nOverwrite? (y/N): ")
            if response.lower() != 'y':
                print("Cancelled")
                return
        
        # Validate inputs
        if not git_url:
            print(f"{Colors.RED}✗ Git URL is required{Colors.RESET}")
            sys.exit(1)
        
        if not contract_path:
            print(f"{Colors.RED}✗ Contract path is required{Colors.RESET}")
            sys.exit(1)
        
        # Create dependency
        dependency = Dependency(
            name=name,
            type="http-api",
            sync_method="git",
            git_url=git_url,
            contract_path=contract_path,
            local_cache=f".kiro/contracts/{name}-api.yaml",
            sync_on_commit=True
        )
        
        # Add to configuration
        config.add_dependency(name, dependency)
        
        print(f"{Colors.GREEN}✓ Dependency added successfully{Colors.RESET}\n")
        print(f"  Name: {Colors.BOLD}{name}{Colors.RESET}")
        print(f"  Git URL: {git_url}")
        print(f"  Contract Path: {contract_path}")
        print(f"  Local Cache: {dependency.local_cache}")
        print(f"\n{Colors.CYAN}Next step:{Colors.RESET}")
        print(f"  Run 'specsync bridge sync {name}' to fetch the contract")
    
    def sync(self, dependency_name: Optional[str] = None) -> None:
        """
        Sync contracts from dependencies.
        
        Args:
            dependency_name: Name of specific dependency to sync (None = sync all)
        """
        # Load configuration
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized{Colors.RESET}")
            print(f"  Run 'specsync bridge init' first")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        if not config.list_dependencies():
            print(f"{Colors.YELLOW}⚠  No dependencies configured{Colors.RESET}")
            print(f"  Add dependencies with 'specsync bridge add-dependency'")
            return
        
        # Create sync engine with progress callback
        def progress_callback(dep_name: str, status: str):
            if status == "starting":
                print(f"  {Colors.CYAN}→{Colors.RESET} Syncing {dep_name}...")
            elif status == "completed":
                print(f"  {Colors.GREEN}✓{Colors.RESET} Completed {dep_name}")
            elif status == "failed":
                print(f"  {Colors.RED}✗{Colors.RESET} Failed {dep_name}")
        
        engine = SyncEngine(config, str(self.repo_root), progress_callback)
        
        # Sync single dependency or all
        if dependency_name:
            print(f"{Colors.BOLD}Syncing dependency: {dependency_name}{Colors.RESET}\n")
            results = [engine.sync_dependency(dependency_name)]
        else:
            print(f"{Colors.BOLD}Syncing all dependencies...{Colors.RESET}\n")
            results = engine.sync_all_dependencies()
        
        # Display results
        print(f"\n{Colors.BOLD}Sync Results:{Colors.RESET}\n")
        
        success_count = 0
        failure_count = 0
        
        for result in results:
            if result.success:
                success_count += 1
                print(f"{Colors.GREEN}✓ {result.dependency_name}{Colors.RESET}")
                print(f"  Endpoints: {result.endpoint_count}")
                print(f"  Cached: {result.cached_file}")
                
                if result.changes:
                    # Check if this is a warning (offline mode)
                    if any('⚠️' in change for change in result.changes):
                        print(f"  {Colors.YELLOW}Warning:{Colors.RESET} {result.changes[0]}")
                    elif result.changes:
                        print(f"  Changes:")
                        for change in result.changes[:5]:  # Show first 5 changes
                            print(f"    - {change}")
                        if len(result.changes) > 5:
                            print(f"    ... and {len(result.changes) - 5} more")
                print()
            else:
                failure_count += 1
                print(f"{Colors.RED}✗ {result.dependency_name}{Colors.RESET}")
                for error in result.errors:
                    print(f"  Error: {error}")
                print()
        
        # Summary
        print(f"{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Success: {Colors.GREEN}{success_count}{Colors.RESET}")
        print(f"  Failed: {Colors.RED}{failure_count}{Colors.RESET}")
        
        if failure_count > 0:
            sys.exit(1)
    
    def validate(self) -> None:
        """
        Validate API calls against cached contracts.
        
        Runs drift detection on all dependencies and displays results.
        """
        print(f"{Colors.BOLD}Validating API calls against contracts...{Colors.RESET}\n")
        
        # Load configuration
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized{Colors.RESET}")
            print(f"  Run 'specsync bridge init' first")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        if not config.list_dependencies():
            print(f"{Colors.YELLOW}⚠  No dependencies configured{Colors.RESET}")
            print(f"  Add dependencies with 'specsync bridge add-dependency'")
            return
        
        # Create drift detector
        detector = BridgeDriftDetector(str(self.repo_root))
        
        # Detect drift for all dependencies
        drift_results = detector.detect_all_drift()
        
        # Display results for each dependency
        total_issues = 0
        total_errors = 0
        total_warnings = 0
        
        for dep_name, issues in drift_results.items():
            print(f"{Colors.BOLD}Dependency: {dep_name}{Colors.RESET}")
            
            if not issues:
                print(f"  {Colors.GREEN}✓ All API calls align with contract{Colors.RESET}\n")
                continue
            
            # Count issues by severity
            errors = [i for i in issues if i.severity == "error"]
            warnings = [i for i in issues if i.severity == "warning"]
            
            total_issues += len(issues)
            total_errors += len(errors)
            total_warnings += len(warnings)
            
            print(f"  {Colors.RED}✗ Found {len(issues)} drift issue(s){Colors.RESET}")
            print(f"    Errors: {len(errors)}, Warnings: {len(warnings)}\n")
            
            # Display each issue
            for i, issue in enumerate(issues, 1):
                severity_color = Colors.RED if issue.severity == "error" else Colors.YELLOW
                print(f"  {i}. [{severity_color}{issue.severity.upper()}{Colors.RESET}] {issue.type}")
                print(f"     Endpoint: {issue.method} {issue.endpoint}")
                print(f"     Location: {Colors.GRAY}{issue.location}{Colors.RESET}")
                print(f"     Message: {issue.message}")
                print(f"     Suggestion: {Colors.CYAN}{issue.suggestion}{Colors.RESET}")
                print()
        
        # Summary
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}Validation Summary{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        
        if total_issues == 0:
            print(f"{Colors.GREEN}✓ SUCCESS - All API calls align with contracts{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ DRIFT DETECTED{Colors.RESET}")
            print(f"  Total Issues: {total_issues}")
            print(f"  Errors: {total_errors}")
            print(f"  Warnings: {total_warnings}")
            print(f"\n{Colors.CYAN}Recommendation:{Colors.RESET}")
            print(f"  1. Sync contracts: specsync bridge sync")
            print(f"  2. Fix API calls to match contracts")
            print(f"  3. Or update provider contracts if changes are intentional")
            sys.exit(1)
    
    def status(self) -> None:
        """
        Display status of all dependencies.
        
        Shows:
        - Configured dependencies
        - Last sync time
        - Endpoint counts
        - Drift status
        """
        print(f"{Colors.BOLD}SpecSync Bridge Status{Colors.RESET}\n")
        
        # Load configuration
        if not self.config_path.exists():
            print(f"{Colors.YELLOW}⚠  Bridge not initialized{Colors.RESET}")
            print(f"  Run 'specsync bridge init' to get started")
            return
        
        config = load_config(str(self.config_path))
        
        # Display configuration info
        print(f"{Colors.BOLD}Configuration:{Colors.RESET}")
        print(f"  Role: {config.role}")
        print(f"  Config: {self.config_path}")
        print()
        
        # Check if there are dependencies
        dependencies = config.list_dependencies()
        
        if not dependencies:
            print(f"{Colors.YELLOW}⚠  No dependencies configured{Colors.RESET}")
            print(f"\n{Colors.CYAN}Next steps:{Colors.RESET}")
            print(f"  1. Add a dependency:")
            print(f"     specsync bridge add-dependency <name> --git-url <url>")
            print(f"  2. Sync contracts:")
            print(f"     specsync bridge sync")
            return
        
        # Display each dependency
        print(f"{Colors.BOLD}Dependencies ({len(dependencies)}):{Colors.RESET}\n")
        
        detector = BridgeDriftDetector(str(self.repo_root))
        
        for dep_name in dependencies:
            dep = config.get_dependency(dep_name)
            cache_path = self.repo_root / dep.local_cache
            
            print(f"{Colors.BOLD}{dep_name}{Colors.RESET}")
            print(f"  Git URL: {dep.git_url}")
            print(f"  Contract Path: {dep.contract_path}")
            print(f"  Local Cache: {dep.local_cache}")
            
            # Check if contract is cached
            if cache_path.exists():
                try:
                    contract = load_contract_from_yaml(str(cache_path))
                    endpoint_count = len(contract.endpoints)
                    last_updated = contract.last_updated
                    
                    print(f"  {Colors.GREEN}✓ Synced{Colors.RESET}")
                    print(f"  Endpoints: {endpoint_count}")
                    print(f"  Last Updated: {self._format_timestamp(last_updated)}")
                    
                    # Check drift status
                    issues = detector.detect_drift(dep_name)
                    if issues:
                        errors = sum(1 for i in issues if i.severity == "error")
                        warnings = sum(1 for i in issues if i.severity == "warning")
                        print(f"  Drift: {Colors.RED}✗ {len(issues)} issue(s){Colors.RESET} ({errors} errors, {warnings} warnings)")
                    else:
                        print(f"  Drift: {Colors.GREEN}✓ No drift{Colors.RESET}")
                    
                except Exception as e:
                    print(f"  {Colors.RED}✗ Error loading contract{Colors.RESET}")
                    print(f"  Error: {str(e)}")
            else:
                print(f"  {Colors.YELLOW}⚠  Not synced{Colors.RESET}")
                print(f"  Run: specsync bridge sync {dep_name}")
            
            print()
        
        # Overall status
        print(f"{Colors.BOLD}Overall Status:{Colors.RESET}")
        
        synced_count = sum(1 for dep_name in dependencies 
                          if (self.repo_root / config.get_dependency(dep_name).local_cache).exists())
        
        if synced_count == len(dependencies):
            print(f"  {Colors.GREEN}✓ All dependencies synced{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}⚠  {len(dependencies) - synced_count} dependencies need syncing{Colors.RESET}")
    
    def _format_timestamp(self, timestamp: str) -> str:
        """
        Format ISO timestamp for display.
        
        Args:
            timestamp: ISO 8601 timestamp
            
        Returns:
            Human-readable timestamp
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo)
            delta = now - dt
            
            if delta.days > 0:
                return f"{delta.days} day(s) ago"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours} hour(s) ago"
            elif delta.seconds > 60:
                minutes = delta.seconds // 60
                return f"{minutes} minute(s) ago"
            else:
                return "just now"
        except:
            return timestamp


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="SpecSync Bridge - Cross-repository API contract synchronization",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize bridge configuration')
    init_parser.add_argument(
        '--role',
        choices=['consumer', 'provider', 'both'],
        default='consumer',
        help='Role of this repository (default: consumer)'
    )
    
    # Add-dependency command
    add_parser = subparsers.add_parser('add-dependency', help='Add a new dependency')
    add_parser.add_argument('name', help='Name of the dependency')
    add_parser.add_argument('--git-url', required=True, help='Git repository URL')
    add_parser.add_argument(
        '--contract-path',
        default='.kiro/contracts/provided-api.yaml',
        help='Path to contract file in dependency repo (default: .kiro/contracts/provided-api.yaml)'
    )
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync contracts from dependencies')
    sync_parser.add_argument(
        'dependency',
        nargs='?',
        help='Name of specific dependency to sync (omit to sync all)'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate API calls against contracts')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show status of all dependencies')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create CLI instance
    cli = BridgeCLI()
    
    # Execute command
    try:
        if args.command == 'init':
            cli.init(role=args.role)
        elif args.command == 'add-dependency':
            cli.add_dependency(args.name, args.git_url, args.contract_path)
        elif args.command == 'sync':
            cli.sync(args.dependency)
        elif args.command == 'validate':
            cli.validate()
        elif args.command == 'status':
            cli.status()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Operation cancelled{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}✗ Error: {str(e)}{Colors.RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()
