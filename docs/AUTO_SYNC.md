# Auto-Sync Feature

SpecSync Bridge supports automatic contract synchronization to keep your consumer repositories up-to-date with provider contracts without manual intervention.

## Overview

Auto-sync automatically fetches the latest contracts from your dependencies:
- **On IDE startup** - Sync when you open your project
- **At intervals** - Sync every 30min, 1h, 2h, 3h, or 6h
- **Silent mode** - Run in background without interrupting your work
- **Smart notifications** - Get notified only when contracts change

## Configuration

### Enable Auto-Sync

```bash
specsync-bridge auto-sync --enable
```

### Configure Interval

```bash
# Sync every hour (default)
specsync-bridge auto-sync --interval 1h

# Sync every 30 minutes
specsync-bridge auto-sync --interval 30min

# Sync every 2 hours
specsync-bridge auto-sync --interval 2h

# Sync every 6 hours
specsync-bridge auto-sync --interval 6h

# Disable interval sync (only on startup)
specsync-bridge auto-sync --interval none
```

### Configure Startup Sync

```bash
# Enable sync on IDE startup (default)
specsync-bridge auto-sync --on-startup true

# Disable sync on IDE startup
specsync-bridge auto-sync --on-startup false
```

### Configure Notifications

```bash
# Enable notifications when contracts change (default)
specsync-bridge auto-sync --notify true

# Disable notifications (silent mode)
specsync-bridge auto-sync --silent true
```

### Disable Auto-Sync

```bash
specsync-bridge auto-sync --disable
```

## Configuration File

Auto-sync settings are stored in `.kiro/settings/bridge.json`:

```json
{
  "bridge": {
    "enabled": true,
    "role": "consumer",
    "auto_sync": {
      "enabled": true,
      "on_startup": true,
      "interval": "1h",
      "silent": true,
      "notify_on_changes": true
    },
    "dependencies": {
      "backend": {
        "name": "backend",
        "type": "http-api",
        "sync_method": "git",
        "git_url": "https://github.com/org/backend.git",
        "contract_path": ".kiro/contracts/provided-api.yaml",
        "local_cache": ".kiro/contracts/backend-api.yaml"
      }
    }
  }
}
```

## Use Cases

### Development Workflow

**Scenario:** You're working on a frontend that consumes a backend API.

**Configuration:**
```bash
specsync-bridge auto-sync --enable --interval 1h --notify true
```

**Benefit:** You'll be notified within an hour when the backend team updates their API contract, allowing you to adapt your code proactively.

### CI/CD Pipeline

**Scenario:** Automated builds need to validate against latest contracts.

**Configuration:**
```bash
specsync-bridge auto-sync --enable --on-startup true --interval none --silent true
```

**Benefit:** Contracts sync at build start, ensuring validation uses the latest contracts without manual sync commands.

### Microservices Architecture

**Scenario:** Multiple services depend on each other's contracts.

**Configuration:**
```bash
specsync-bridge auto-sync --enable --interval 30min --notify true
```

**Benefit:** Frequent syncs catch breaking changes quickly, reducing integration issues.

### Offline Development

**Scenario:** Working without reliable internet connection.

**Configuration:**
```bash
specsync-bridge auto-sync --disable
```

**Benefit:** No failed sync attempts. Use cached contracts and manually sync when online.

## Interval Options

| Interval | Seconds | Use Case |
|----------|---------|----------|
| `none` | - | Manual sync only, or startup-only |
| `30min` | 1800 | Fast-moving APIs, tight integration |
| `1h` | 3600 | Active development (default) |
| `2h` | 7200 | Balanced sync frequency |
| `3h` | 10800 | Stable APIs, less frequent changes |
| `6h` | 21600 | Very stable APIs, rare changes |

## Behavior

### Startup Sync

When `on_startup` is enabled:
1. IDE opens your project
2. Bridge checks for configured dependencies
3. Syncs all dependencies in parallel
4. Caches contracts locally
5. Notifies if changes detected (if `notify_on_changes` is true)

### Interval Sync

When `interval` is set:
1. Timer starts after IDE opens
2. At each interval, Bridge syncs all dependencies
3. Uses cached contracts if git fetch fails
4. Notifies only if contracts changed (if `notify_on_changes` is true)

### Silent Mode

When `silent` is true:
- No progress indicators shown
- Syncs happen in background
- Notifications still shown if `notify_on_changes` is true
- Errors logged but not displayed

### Offline Fallback

If git sync fails (network issues, repo unavailable):
- Uses cached contracts from previous sync
- No error notifications in silent mode
- Validation continues with cached contracts
- Next sync attempt at next interval

## MCP Integration

Kiro can configure auto-sync via MCP tools:

```typescript
// Enable auto-sync with 1-hour interval
await mcp.call("bridge_auto_sync", {
  enable: true,
  interval: "1h",
  on_startup: true,
  notify: true
});

// Disable auto-sync
await mcp.call("bridge_auto_sync", {
  disable: true
});
```

## Best Practices

### For Consumers

1. **Enable auto-sync** - Stay up-to-date automatically
2. **Set appropriate interval** - Balance freshness vs. network usage
3. **Enable notifications** - Know when contracts change
4. **Use silent mode** - Avoid interruptions during focused work

### For Providers

1. **Version your contracts** - Use semantic versioning
2. **Document breaking changes** - Help consumers adapt
3. **Test before pushing** - Ensure contracts are valid
4. **Communicate updates** - Notify consumers of major changes

### For Teams

1. **Standardize intervals** - Team-wide consistency
2. **Document dependencies** - Clear contract relationships
3. **Monitor sync status** - Check for sync failures
4. **Review notifications** - Act on contract changes promptly

## Troubleshooting

### Auto-sync not working

Check configuration:
```bash
specsync-bridge status
```

Verify auto-sync is enabled in `.kiro/settings/bridge.json`.

### Contracts not updating

1. Check git URL is accessible
2. Verify provider pushed contract changes
3. Check network connectivity
4. Review sync logs

### Too many notifications

Reduce notification frequency:
```bash
specsync-bridge auto-sync --interval 6h
```

Or disable notifications:
```bash
specsync-bridge auto-sync --notify false
```

### Performance impact

If auto-sync affects IDE performance:
1. Increase interval: `--interval 6h`
2. Disable startup sync: `--on-startup false`
3. Enable silent mode: `--silent true`

## Future Enhancements

Planned features:
- **Selective sync** - Sync only specific dependencies
- **Webhook support** - Instant sync on provider updates
- **Sync history** - View past sync operations
- **Conflict resolution** - Handle contract conflicts automatically
- **Bandwidth optimization** - Delta syncs for large contracts

## Examples

### Example 1: Active Development

```bash
# Initialize consumer
specsync-bridge init --role consumer

# Add backend dependency
specsync-bridge add-dependency backend --git-url https://github.com/org/backend.git

# Enable auto-sync with default settings (1h interval, startup sync, silent mode)
specsync-bridge auto-sync --enable --notify true

# Check status
specsync-bridge status
```

### Example 2: CI/CD Pipeline

```bash
# In your CI script
specsync-bridge auto-sync --enable --on-startup true --interval none --silent true
specsync-bridge sync
specsync-bridge validate
```

### Example 3: Offline Development

```bash
# Before going offline
specsync-bridge sync  # Cache latest contracts

# Disable auto-sync
specsync-bridge auto-sync --disable

# Work offline with cached contracts
specsync-bridge validate  # Uses cached contracts

# When back online
specsync-bridge auto-sync --enable
specsync-bridge sync
```

## Summary

Auto-sync keeps your consumer repositories synchronized with provider contracts automatically, reducing manual work and catching breaking changes early. Configure it once and let Bridge handle the rest.

**Quick Start:**
```bash
specsync-bridge auto-sync --enable
```

That's it! Your contracts will now sync automatically every hour and on IDE startup in silent mode with notifications on changes.
