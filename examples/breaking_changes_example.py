"""
Example demonstrating breaking change detection in SpecSync Bridge.

This example shows how providers can detect breaking changes when
modifying their API contracts.
"""
from backend.bridge_models import Contract, Endpoint
from backend.bridge_breaking_changes import (
    BreakingChangeDetector,
    format_breaking_changes
)


def main():
    """Demonstrate breaking change detection."""
    
    # Create an old contract with consumers
    old_contract = Contract(
        version="1.0",
        repo_id="backend",
        role="provider",
        last_updated="2024-11-27T10:00:00Z",
        endpoints=[
            Endpoint(
                id="get-user",
                path="/users/{id}",
                method="GET",
                consumers=["frontend", "mobile"]
            ),
            Endpoint(
                id="list-users",
                path="/users",
                method="GET",
                consumers=["frontend"]
            ),
            Endpoint(
                id="delete-user",
                path="/users/{id}",
                method="DELETE",
                consumers=["admin-panel"]
            ),
            Endpoint(
                id="unused-endpoint",
                path="/admin/stats",
                method="GET",
                consumers=[]
            )
        ]
    )
    
    # Create a new contract with changes
    new_contract = Contract(
        version="1.0",
        repo_id="backend",
        role="provider",
        last_updated="2024-11-27T11:00:00Z",
        endpoints=[
            Endpoint(
                id="get-user",
                path="/users/{id}",
                method="GET",
                parameters=[{"name": "include_posts", "type": "boolean"}],  # Modified
                consumers=["frontend", "mobile"]
            ),
            Endpoint(
                id="list-users",
                path="/users",
                method="GET",
                consumers=["frontend"]
            )
            # delete-user endpoint removed
            # unused-endpoint removed
        ]
    )
    
    # Detect breaking changes
    detector = BreakingChangeDetector()
    changes = detector.detect_breaking_changes(old_contract, new_contract)
    
    # Format and display results
    print(format_breaking_changes(changes))
    
    # Analyze the results
    print("\nAnalysis:")
    print(f"Total changes detected: {len(changes)}")
    
    errors = [c for c in changes if c.severity == "error"]
    warnings = [c for c in changes if c.severity == "warning"]
    info = [c for c in changes if c.severity == "info"]
    
    print(f"  - Errors (breaking changes): {len(errors)}")
    print(f"  - Warnings (potential issues): {len(warnings)}")
    print(f"  - Info (safe changes): {len(info)}")
    
    if errors:
        print("\n⚠️  ATTENTION: Breaking changes detected!")
        print("These changes will affect consumers and require coordination:")
        for error in errors:
            print(f"  - {error.endpoint}: {', '.join(error.affected_consumers)}")


if __name__ == '__main__':
    main()
