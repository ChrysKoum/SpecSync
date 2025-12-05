"""
CLI interface for SpecSync Bridge.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

from specsync_bridge.models import BridgeConfig, Dependency, load_config, load_contract_from_yaml
from specsync_bridge.sync import SyncEngine
from specsync_bridge.detector import BridgeDriftDetector
from specsync_bridge.extractor import extract_provider_contract, detect_repo_role
from specsync_bridge.setup_wizard import setup_wizard


class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'


class BridgeCLI:
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.config_path = self.repo_root / ".kiro/settings/bridge.json"
    
    def init(self, role: str = "consumer"):
        print(f"{Colors.BOLD}Initializing SpecSync Bridge...{Colors.RESET}\n")
        
        if role not in ['consumer', 'provider', 'both']:
            print(f"{Colors.RED}✗ Invalid role: {role}{Colors.RESET}")
            sys.exit(1)
        
        config = BridgeConfig.create_default(role=role, config_path=str(self.config_path))
        config.save()
        
        contracts_dir = self.repo_root / ".kiro/contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"{Colors.GREEN}✓ Bridge initialized{Colors.RESET}")
        print(f"  Role: {role}")
        print(f"  Config: {self.config_path}")
        
        if role in ['provider', 'both']:
            print(f"\n{Colors.CYAN}Next: Run 'specsync-bridge extract' to create your contract{Colors.RESET}")
        if role in ['consumer', 'both']:
            print(f"\n{Colors.CYAN}Next: Run 'specsync-bridge add-dependency <name> --git-url <url>'{Colors.RESET}")
    
    def add_dependency(self, name: str, git_url: str, contract_path: str = ".kiro/contracts/provided-api.yaml"):
        print(f"{Colors.BOLD}Adding dependency: {name}{Colors.RESET}\n")
        
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized. Run 'specsync-bridge init' first{Colors.RESET}")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        dependency = Dependency(
            name=name,
            type="http-api",
            sync_method="git",
            git_url=git_url,
            contract_path=contract_path,
            local_cache=f".kiro/contracts/{name}-api.yaml",
            sync_on_commit=True
        )
        
        config.add_dependency(name, dependency)
        
        print(f"{Colors.GREEN}✓ Dependency added{Colors.RESET}")
        print(f"  Name: {name}")
        print(f"  Git URL: {git_url}")
        print(f"\n{Colors.CYAN}Next: Run 'specsync-bridge sync {name}'{Colors.RESET}")
    
    def sync(self, dependency_name: str = None):
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized{Colors.RESET}")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        if not config.list_dependencies():
            print(f"{Colors.YELLOW}⚠ No dependencies configured{Colors.RESET}")
            return
        
        def progress(name, status):
            if status == "starting":
                print(f"  → Syncing {name}...")
            elif status == "completed":
                print(f"  {Colors.GREEN}✓{Colors.RESET} {name}")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} {name}")
        
        engine = SyncEngine(config, str(self.repo_root), progress)
        
        if dependency_name:
            print(f"{Colors.BOLD}Syncing: {dependency_name}{Colors.RESET}\n")
            results = [engine.sync_dependency(dependency_name)]
        else:
            print(f"{Colors.BOLD}Syncing all dependencies...{Colors.RESET}\n")
            results = engine.sync_all_dependencies()
        
        print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
        for r in results:
            if r.success:
                print(f"  {Colors.GREEN}✓{Colors.RESET} {r.dependency_name}: {r.endpoint_count} endpoints")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} {r.dependency_name}: {', '.join(r.errors)}")
    
    def validate(self):
        print(f"{Colors.BOLD}Validating API calls...{Colors.RESET}\n")
        
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized{Colors.RESET}")
            sys.exit(1)
        
        detector = BridgeDriftDetector(str(self.repo_root))
        results = detector.detect_all_drift()
        
        total_issues = 0
        for dep_name, issues in results.items():
            if not issues:
                print(f"  {Colors.GREEN}✓{Colors.RESET} {dep_name}: No drift")
            else:
                total_issues += len(issues)
                print(f"  {Colors.RED}✗{Colors.RESET} {dep_name}: {len(issues)} issue(s)")
                for issue in issues[:3]:
                    print(f"    - {issue.method} {issue.endpoint} ({issue.location})")
        
        if total_issues == 0:
            print(f"\n{Colors.GREEN}✓ All API calls align with contracts{Colors.RESET}")
        else:
            print(f"\n{Colors.RED}✗ {total_issues} drift issue(s) found{Colors.RESET}")
            sys.exit(1)
    
    def status(self):
        print(f"{Colors.BOLD}SpecSync Bridge Status{Colors.RESET}\n")
        
        if not self.config_path.exists():
            print(f"{Colors.YELLOW}⚠ Bridge not initialized{Colors.RESET}")
            print(f"  Run 'specsync-bridge init' to get started")
            return
        
        config = load_config(str(self.config_path))
        print(f"Role: {config.role}")
        print(f"Config: {self.config_path}\n")
        
        deps = config.list_dependencies()
        if not deps:
            print(f"{Colors.YELLOW}No dependencies configured{Colors.RESET}")
            return
        
        print(f"{Colors.BOLD}Dependencies ({len(deps)}):{Colors.RESET}")
        for name in deps:
            dep = config.get_dependency(name)
            cache = self.repo_root / dep.local_cache
            print(f"\n  {Colors.BOLD}{name}{Colors.RESET}")
            print(f"    URL: {dep.git_url}")
            if cache.exists():
                print(f"    Status: {Colors.GREEN}Synced{Colors.RESET}")
            else:
                print(f"    Status: {Colors.YELLOW}Not synced{Colors.RESET}")
    
    def extract(self):
        print(f"{Colors.BOLD}Extracting API contract...{Colors.RESET}\n")
        output = extract_provider_contract(str(self.repo_root))
        print(f"{Colors.GREEN}✓ Contract saved to: {output}{Colors.RESET}")
    
    def detect(self):
        print(f"{Colors.BOLD}Detecting repository role...{Colors.RESET}\n")
        result = detect_repo_role(str(self.repo_root))
        
        role = result['role']
        if role == "provider":
            color = Colors.CYAN
        elif role == "consumer":
            color = Colors.YELLOW
        elif role == "both":
            color = Colors.GREEN
        else:
            color = Colors.RED
        
        print(f"  Detected Role: {color}{role.upper()}{Colors.RESET}")
        print(f"  API Endpoints: {result['endpoint_count']}")
        print(f"  API Calls: {result['api_call_count']}")
        print(f"\n  {result['suggestion']}")
        
        if role != "unknown":
            print(f"\n{Colors.CYAN}Suggested next step:{Colors.RESET}")
            print(f"  specsync-bridge init --role {role}")
        
        return result
    
    def configure_auto_sync(self, args):
        print(f"{Colors.BOLD}Configuring auto-sync...{Colors.RESET}\n")
        
        if not self.config_path.exists():
            print(f"{Colors.RED}✗ Bridge not initialized. Run 'specsync-bridge init' first{Colors.RESET}")
            sys.exit(1)
        
        config = load_config(str(self.config_path))
        
        # Handle enable/disable
        if args.enable:
            config.auto_sync.enabled = True
        elif args.disable:
            config.auto_sync.enabled = False
        
        # Update settings if provided
        if args.interval is not None:
            config.auto_sync.interval = args.interval
        if args.on_startup is not None:
            config.auto_sync.on_startup = args.on_startup
        if args.silent is not None:
            config.auto_sync.silent = args.silent
        if args.notify is not None:
            config.auto_sync.notify_on_changes = args.notify
        
        config.save()
        
        # Display current configuration
        status_icon = f"{Colors.GREEN}✓ ENABLED{Colors.RESET}" if config.auto_sync.enabled else f"{Colors.YELLOW}✗ DISABLED{Colors.RESET}"
        print(f"  Status: {status_icon}")
        print(f"  Sync on startup: {config.auto_sync.on_startup}")
        print(f"  Interval: {config.auto_sync.interval or 'none'}")
        print(f"  Silent mode: {config.auto_sync.silent}")
        print(f"  Notify on changes: {config.auto_sync.notify_on_changes}")
        
        if config.auto_sync.enabled:
            interval_desc = config.auto_sync.interval if config.auto_sync.interval != "none" else "manual only"
            print(f"\n{Colors.GREEN}✓ Auto-sync configured{Colors.RESET}")
            print(f"  Contracts will sync on IDE startup and every {interval_desc}")
        else:
            print(f"\n{Colors.YELLOW}Auto-sync is disabled{Colors.RESET}")
            print(f"  Run 'specsync-bridge auto-sync --enable' to enable")


def main():
    parser = argparse.ArgumentParser(
        description="SpecSync Bridge - Cross-repository API contract sync",
        prog="specsync-bridge"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # init
    init_p = subparsers.add_parser('init', help='Initialize bridge')
    init_p.add_argument('--role', choices=['consumer', 'provider', 'both'], default='consumer')
    
    # add-dependency
    add_p = subparsers.add_parser('add-dependency', help='Add dependency')
    add_p.add_argument('name', help='Dependency name')
    add_p.add_argument('--git-url', required=True, help='Git URL')
    add_p.add_argument('--contract-path', default='.kiro/contracts/provided-api.yaml')
    
    # sync
    sync_p = subparsers.add_parser('sync', help='Sync contracts')
    sync_p.add_argument('dependency', nargs='?', help='Specific dependency')
    
    # validate
    subparsers.add_parser('validate', help='Validate API calls')
    
    # status
    subparsers.add_parser('status', help='Show status')
    
    # extract
    subparsers.add_parser('extract', help='Extract provider contract')
    
    # detect
    subparsers.add_parser('detect', help='Auto-detect if repo is provider or consumer')
    
    # setup
    subparsers.add_parser('setup', help='Interactive setup wizard')
    
    # auto-sync
    auto_sync_p = subparsers.add_parser('auto-sync', help='Configure auto-sync')
    auto_sync_p.add_argument('--enable', action='store_true', help='Enable auto-sync')
    auto_sync_p.add_argument('--disable', action='store_true', help='Disable auto-sync')
    auto_sync_p.add_argument('--interval', choices=['none', '30min', '1h', '2h', '3h', '6h'], help='Sync interval')
    auto_sync_p.add_argument('--on-startup', type=lambda x: x.lower() == 'true', help='Sync on IDE startup (true/false)')
    auto_sync_p.add_argument('--silent', type=lambda x: x.lower() == 'true', help='Silent mode (true/false)')
    auto_sync_p.add_argument('--notify', type=lambda x: x.lower() == 'true', help='Notify on changes (true/false)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = BridgeCLI()
    
    if args.command == 'init':
        cli.init(args.role)
    elif args.command == 'add-dependency':
        cli.add_dependency(args.name, args.git_url, args.contract_path)
    elif args.command == 'sync':
        cli.sync(args.dependency)
    elif args.command == 'validate':
        cli.validate()
    elif args.command == 'status':
        cli.status()
    elif args.command == 'extract':
        cli.extract()
    elif args.command == 'detect':
        cli.detect()
    elif args.command == 'setup':
        setup_wizard()
    elif args.command == 'auto-sync':
        cli.configure_auto_sync(args)


if __name__ == '__main__':
    main()
