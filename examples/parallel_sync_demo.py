"""
Demonstration of parallel sync for multiple dependencies.

This example shows how the SyncEngine syncs multiple dependencies
concurrently with progress tracking and partial failure handling.
"""
from backend.bridge_sync import SyncEngine
from backend.bridge_models import BridgeConfig, Dependency


def progress_callback(dep_name: str, status: str):
    """Callback to track sync progress."""
    status_emoji = {
        'starting': '🔄',
        'completed': '✅',
        'failed': '❌'
    }
    emoji = status_emoji.get(status, '❓')
    print(f"{emoji} {dep_name}: {status}")


def main():
    """Demonstrate parallel sync."""
    print("=" * 60)
    print("Parallel Sync Demonstration")
    print("=" * 60)
    
    # Create a config with multiple dependencies
    config = BridgeConfig(role="consumer", repo_id="demo-consumer")
    
    # Add multiple dependencies
    dependencies = [
        ("backend-api", "https://github.com/org/backend.git"),
        ("auth-service", "https://github.com/org/auth.git"),
        ("payment-service", "https://github.com/org/payment.git"),
        ("notification-service", "https://github.com/org/notification.git"),
    ]
    
    for name, git_url in dependencies:
        dep = Dependency(
            name=name,
            type="http-api",
            sync_method="git",
            git_url=git_url,
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=f".kiro/contracts/{name}.yaml"
        )
        config.dependencies[name] = dep
    
    print(f"\nConfigured {len(dependencies)} dependencies")
    print(f"Max concurrent syncs: {SyncEngine.MAX_CONCURRENT_SYNCS}")
    print("\nStarting parallel sync...\n")
    
    # Create sync engine with progress callback
    engine = SyncEngine(config, progress_callback=progress_callback)
    
    # Sync all dependencies in parallel
    results = engine.sync_all_dependencies()
    
    # Report results
    print("\n" + "=" * 60)
    print("Sync Results")
    print("=" * 60)
    
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for result in successful:
        print(f"   - {result.dependency_name}: {result.endpoint_count} endpoints")
        if result.changes:
            for change in result.changes[:3]:  # Show first 3 changes
                print(f"     • {change}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for result in failed:
            print(f"   - {result.dependency_name}")
            for error in result.errors[:2]:  # Show first 2 errors
                print(f"     • {error}")
    
    print("\n" + "=" * 60)
    print("Key Features Demonstrated:")
    print("=" * 60)
    print("✓ Concurrent sync execution using ThreadPoolExecutor")
    print("✓ Progress tracking for each dependency")
    print("✓ Partial failure handling (continue on individual failures)")
    print("✓ Per-dependency status reports")
    print(f"✓ Limited to {SyncEngine.MAX_CONCURRENT_SYNCS} concurrent syncs")
    print()


if __name__ == '__main__':
    main()
