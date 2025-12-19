# Changelog

All notable changes to DDI Toolkit will be documented in this file.

## [Unreleased]

## [1.2.0] - 2025-12-18

### Added
- **Intelligent Search** - Auto-detection of input type (IP, CIDR, MAC, FQDN, Zone, text)
- **Type Prefix Support** - Force specific search types with prefixes:
  - `host:` - Host records only
  - `ptr:` - PTR records only
  - `a:` - A records only
  - `cname:` - CNAME records only
  - `mx:`, `txt:`, `srv:`, `ns:` - Respective DNS records
  - `zone:` - Zones only
  - `ip:` - IP address details only
  - `mac:` - Fixed addresses/leases by MAC
  - `net:` - Networks and containers
  - `all:` - Full search (all types)
- **Interactive Refinement** - Post-search options:
  - `[P]` PTR lookup (for IP searches)
  - `[Z]` Zone info (for FQDN searches)
  - `[E]` Expand to full search
  - `[N]` New search
- **Search Suggestions** - Helpful suggestions when no results found
- 28 new tests for intelligent search functionality

### Changed
- Refactored `lib/` to `ddi_toolkit/` for proper Python packaging
- Added `pyproject.toml` for modern Python packaging
- Search menu now shows type prefix hints
- Search displays detected input type before querying

## [1.1.0] - 2025-12-18

### Added
- **Dual Audit Sources** - Audit data retrieved from Splunk (primary) or WAPI fileop (fallback)
- **WAPI Fileop Audit** - Downloads audit logs directly from InfoBlox when Splunk unavailable
- **Splunk Username/Password Auth** - Support for Splunk authentication via username/password (in addition to API token)
- **Audit Log Caching** - 5-minute cache for downloaded audit logs to improve performance
- **Timestamp Parsing** - Robust parsing for ISO, Unix, and string timestamp formats
- **Error Logging** - Added logging module to audit.py for better debugging
- Comprehensive quiet mode test script (`scripts/test_quiet_mode.py`)

### Fixed
- Timestamp parsing for various formats (ISO with/without Z, Unix timestamps)
- Silent failures in archive parsing now logged properly
- Container test field name (was "container", now "network")

## [1.0.0] - 2025-12-17

### Added
- **Interactive TUI** - Menu-driven interface for guided queries
- **Quiet Mode** - Scripting-friendly with `-q` flag, outputs JSON file path
- **Network View Support** - Query default view, all views, or specific views
- **Commands**:
  - `network` - Query network details, DHCP pools, utilization
  - `ip` - Query IP status, bindings, conflicts, DNS records
  - `zone` - Query DNS zone configuration, record counts
  - `container` - Query network container hierarchy
  - `dhcp` - Query DHCP ranges, leases, failover status
  - `search` - Global search across all object types
- **Output Formats** - JSON and CSV output for all queries
- **Audit Trail** - Create/modify dates and admin users for all objects
- **Extensible Attributes** - Full extattr support in query results
- Configuration wizard for first-time setup
- SSL verification toggle for self-signed certificates

### Technical
- WAPI v2.13.1 support
- Python 3.8+ compatibility
- Virtual environment setup script
- Comprehensive test suite
