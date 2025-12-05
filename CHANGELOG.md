# Changelog

All notable changes to SpecSync will be documented in this file.

## [0.2.0] - 2025-12-05

### Added
- **Auto-Sync Feature**: Automatic contract synchronization on IDE startup and at configurable intervals
  - Configurable intervals: 30min, 1h, 2h, 3h, 6h, or none
  - Silent mode with optional notifications on changes
  - Default: 1h interval, silent mode, notify on changes
- **Interactive Setup Wizard**: `specsync-bridge setup` command for guided onboarding
  - Auto-detects repository role (provider/consumer/both)
  - Walks through dependency configuration
  - Configures auto-sync interactively
  - Offers immediate sync/extract
- **MCP Auto-Sync Tool**: `bridge_auto_sync` for Kiro IDE integration
- **Enhanced Documentation**:
  - Complete Auto-Sync guide (`docs/AUTO_SYNC.md`)
  - Updated CLI reference with setup wizard
  - Cleaner, more focused README

### Changed
- **Package Versions**:
  - `specsync-bridge`: 0.1.0 → 0.2.0
  - `specsync-mcp`: 1.1.0 → 1.2.0
- **README**: Simplified and focused on quick start
- **Documentation Structure**: Moved implementation docs to `archived-docs/`

### Fixed
- TypeScript type errors in MCP server
- Bridge command execution with arguments

### Archived
Moved to `archived-docs/` (gitignored):
- DEMO_VIDEO_SCRIPT.md
- DEV_TO_BLOG_POST.md
- HACKATHON_PROJECT_STORY.md
- HACKATHON_SUBMISSION_CHECKLIST.md
- KIRO_USAGE.md
- PUBLISHING_GUIDE.md
- SOCIAL_MEDIA_POST.md
- BRIDGE_MANUAL_TESTING.md
- BRIDGE_VALIDATION_SUMMARY.md
- CLI_IMPLEMENTATION_SUMMARY.md

## [0.1.0] - 2025-12-01

### Added
- Initial release of SpecSync Bridge
- Cross-repository API contract synchronization
- Git-based contract sync
- Drift detection and validation
- Provider/consumer role support
- Parallel dependency syncing
- Offline fallback with caching
- Breaking change detection
- MCP server integration
- Complete CLI interface
- Comprehensive test suite (230+ tests)

### Features
- `specsync-bridge init` - Initialize Bridge
- `specsync-bridge add-dependency` - Add dependencies
- `specsync-bridge sync` - Sync contracts
- `specsync-bridge validate` - Validate API calls
- `specsync-bridge status` - Show status
- `specsync-bridge extract` - Extract provider contracts
- `specsync-bridge detect` - Auto-detect repository role
