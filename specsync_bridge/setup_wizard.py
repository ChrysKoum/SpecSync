"""
Interactive setup wizard for SpecSync Bridge.
Makes onboarding seamless with guided prompts.
"""
import sys
from pathlib import Path
from specsync_bridge.models import BridgeConfig, Dependency
from specsync_bridge.extractor import detect_repo_role
from specsync_bridge.sync import SyncEngine


class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'


def prompt(question: str, default: str = None) -> str:
    """Prompt user for input with optional default."""
    if default:
        response = input(f"{Colors.CYAN}? {question} ({default}): {Colors.RESET}")
        return response.strip() or default
    else:
        response = input(f"{Colors.CYAN}? {question}: {Colors.RESET}")
        return response.strip()


def confirm(question: str, default: bool = True) -> bool:
    """Ask yes/no question."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{Colors.CYAN}? {question} ({default_str}): {Colors.RESET}")
    if not response.strip():
        return default
    return response.lower() in ['y', 'yes']


def setup_wizard(repo_root: str = "."):
    """Run interactive setup wizard."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}╔═══════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}║   SpecSync Bridge Setup Wizard           ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}╚═══════════════════════════════════════════╝{Colors.RESET}\n")
    
    print(f"{Colors.YELLOW}This wizard will help you set up SpecSync Bridge in 3 steps:{Colors.RESET}")
    print(f"  1. Detect your repository role")
    print(f"  2. Initialize Bridge configuration")
    print(f"  3. Configure dependencies (if consumer)\n")
    
    # Step 1: Auto-detect role
    print(f"{Colors.BOLD}Step 1: Detecting repository role...{Colors.RESET}\n")
    detection = detect_repo_role(repo_root)
    role = detection['role']
    
    if role == "unknown":
        print(f"{Colors.YELLOW}⚠ Could not auto-detect role{Colors.RESET}")
        print(f"\nPlease choose your role:")
        print(f"  1. Provider - This repo provides APIs")
        print(f"  2. Consumer - This repo calls external APIs")
        print(f"  3. Both - This repo provides and consumes APIs")
        choice = prompt("Enter choice (1-3)", "2")
        role_map = {"1": "provider", "2": "consumer", "3": "both"}
        role = role_map.get(choice, "consumer")
    else:
        print(f"  Detected: {Colors.GREEN}{role.upper()}{Colors.RESET}")
        print(f"  API Endpoints: {detection['endpoint_count']}")
        print(f"  API Calls: {detection['api_call_count']}")
        if not confirm(f"\nIs this correct?", True):
            print(f"\nPlease choose your role:")
            print(f"  1. Provider")
            print(f"  2. Consumer")
            print(f"  3. Both")
            choice = prompt("Enter choice (1-3)", "2")
            role_map = {"1": "provider", "2": "consumer", "3": "both"}
            role = role_map.get(choice, "consumer")
    
    # Step 2: Initialize
    print(f"\n{Colors.BOLD}Step 2: Initializing Bridge...{Colors.RESET}\n")
    config_path = Path(repo_root) / ".kiro/settings/bridge.json"
    config = BridgeConfig.create_default(role=role, config_path=str(config_path))
    
    # Configure auto-sync
    if role in ['consumer', 'both']:
        print(f"\n{Colors.YELLOW}Auto-sync keeps your contracts up-to-date automatically.{Colors.RESET}")
        if confirm("Enable auto-sync?", True):
            config.auto_sync.enabled = True
            print(f"\nChoose sync interval:")
            print(f"  1. Every 30 minutes (fast-moving APIs)")
            print(f"  2. Every hour (default)")
            print(f"  3. Every 2 hours")
            print(f"  4. Every 6 hours")
            print(f"  5. On startup only")
            interval_choice = prompt("Enter choice (1-5)", "2")
            interval_map = {
                "1": "30min",
                "2": "1h",
                "3": "2h",
                "4": "6h",
                "5": "none"
            }
            config.auto_sync.interval = interval_map.get(interval_choice, "1h")
            print(f"  {Colors.GREEN}✓{Colors.RESET} Auto-sync enabled (interval: {config.auto_sync.interval})")
    
    config.save()
    contracts_dir = Path(repo_root) / ".kiro/contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  {Colors.GREEN}✓{Colors.RESET} Bridge initialized")
    print(f"  {Colors.GREEN}✓{Colors.RESET} Config saved to {config_path}")
    
    # Step 3: Add dependencies (for consumers)
    if role in ['consumer', 'both']:
        print(f"\n{Colors.BOLD}Step 3: Configure dependencies{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Add the APIs this repository depends on.{Colors.RESET}\n")
        
        dependencies_added = 0
        while True:
            if dependencies_added > 0:
                if not confirm("Add another dependency?", False):
                    break
            else:
                if not confirm("Add a dependency now?", True):
                    break
            
            print()
            dep_name = prompt("Dependency name (e.g., 'backend', 'auth-service')")
            if not dep_name:
                print(f"{Colors.RED}✗ Name is required{Colors.RESET}")
                continue
            
            git_url = prompt("Git repository URL")
            if not git_url:
                print(f"{Colors.RED}✗ Git URL is required{Colors.RESET}")
                continue
            
            contract_path = prompt("Contract path in repo", ".kiro/contracts/provided-api.yaml")
            
            dependency = Dependency(
                name=dep_name,
                type="http-api",
                sync_method="git",
                git_url=git_url,
                contract_path=contract_path,
                local_cache=f".kiro/contracts/{dep_name}-api.yaml",
                sync_on_commit=True
            )
            
            config.add_dependency(dep_name, dependency)
            print(f"  {Colors.GREEN}✓{Colors.RESET} Added dependency: {dep_name}")
            dependencies_added += 1
        
        # Offer to sync now
        if dependencies_added > 0:
            print()
            if confirm("Sync contracts now?", True):
                print(f"\n{Colors.BOLD}Syncing contracts...{Colors.RESET}\n")
                
                def progress(name, status):
                    if status == "starting":
                        print(f"  → Syncing {name}...")
                    elif status == "completed":
                        print(f"  {Colors.GREEN}✓{Colors.RESET} {name}")
                    else:
                        print(f"  {Colors.RED}✗{Colors.RESET} {name}")
                
                engine = SyncEngine(config, repo_root, progress)
                results = engine.sync_all()
                
                success_count = sum(1 for r in results if r.success)
                print(f"\n  {Colors.GREEN}✓{Colors.RESET} Synced {success_count}/{len(results)} dependencies")
    
    # Step 4: Extract contract (for providers)
    if role in ['provider', 'both']:
        print(f"\n{Colors.BOLD}Step 4: Extract your API contract{Colors.RESET}\n")
        if confirm("Extract contract now?", True):
            from specsync_bridge.extractor import extract_provider_contract
            print(f"\n  → Extracting contract...")
            contract = extract_provider_contract(repo_root)
            contract_file = Path(repo_root) / ".kiro/contracts/provided-api.yaml"
            contract.save_to_yaml(str(contract_file))
            print(f"  {Colors.GREEN}✓{Colors.RESET} Contract extracted")
            print(f"  {Colors.GREEN}✓{Colors.RESET} Saved to {contract_file}")
            print(f"  {Colors.GREEN}✓{Colors.RESET} Found {len(contract.endpoints)} endpoints")
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.GREEN}╔═══════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}║   Setup Complete! 🎉                      ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}╚═══════════════════════════════════════════╝{Colors.RESET}\n")
    
    print(f"{Colors.BOLD}Next steps:{Colors.RESET}")
    if role in ['consumer', 'both']:
        print(f"  • Run {Colors.CYAN}specsync-bridge validate{Colors.RESET} to check for drift")
        print(f"  • Run {Colors.CYAN}specsync-bridge status{Colors.RESET} to view configuration")
    if role in ['provider', 'both']:
        print(f"  • Commit your contract: {Colors.CYAN}git add .kiro/contracts/{Colors.RESET}")
        print(f"  • Push to share with consumers: {Colors.CYAN}git push{Colors.RESET}")
    
    print(f"\n{Colors.YELLOW}Documentation:{Colors.RESET} https://github.com/yourusername/specsync")
    print()
