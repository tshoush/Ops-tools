# DDI Toolkit

A Swiss Army Knife for InfoBlox DDI Engineers. Query networks, IPs, DNS zones, DHCP, and more from the command line with full audit trail support.

## Features

- **Interactive TUI** - Menu-driven interface for guided queries
- **Quiet Mode** - Scripting-friendly with JSON/CSV output
- **Network View Support** - Query default view, all views, or specific views
- **Audit Trail** - Create/modify dates and admin users for all objects
- **Splunk Integration** - Extended audit history (optional)
- **Comprehensive Queries** - Networks, IPs, zones, containers, DHCP

## Quick Start

```bash
# Setup
./setup.sh
source .venv/bin/activate

# Run (first time will prompt for configuration)
./ddi

# Or use quiet mode for scripting
./ddi -q network 10.20.30.0/24
```

See [QUICK_START.md](QUICK_START.md) for detailed setup instructions.

---

## Requirements

- Python 3.8+
- InfoBlox NIOS 9.x with WAPI 2.13.1
- Network access to Grid Master
- Read access credentials

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd ddi-toolkit
```

### 2. Run Setup

```bash
./setup.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Make scripts executable

### 3. Activate Environment

```bash
source .venv/bin/activate
```

### 4. First Run

```bash
./ddi
```

On first run, you'll configure:
- Grid Master IP/hostname
- Admin username and password
- WAPI version
- SSL verification preference
- Splunk integration (optional)

---

## Usage

### Interactive Mode (Default)

```bash
./ddi
```

Navigate with number keys and follow prompts:

```
╔════════════════════════════════════════════╗
║       DDI Toolkit - Marriott DDI Team      ║
║              WAPI v2.13.1                  ║
╚════════════════════════════════════════════╝
  Grid Master: gm.example.com  |  Status: ● Connected
  Network View: default (default)

  QUERY COMMANDS

  [1] Query Network        CIDR, utilization, DHCP pools
  [2] Query IP Address     Status, bindings, conflicts
  [3] Query DNS Zone       Zone details, record counts
  [4] Query Container      Network containers, hierarchy
  [5] Query DHCP           Pools, leases, failover
  [6] Search               Global search across objects

  [V] Network View         Select default, all, or specific
  [C] Configuration        [T] Test Connection
  [H] Help                 [Q] Quit
```

### Quiet Mode (Scripting)

```bash
# Network query
./ddi -q network 10.20.30.0/24

# IP address query
./ddi -q ip 10.20.30.50

# DNS zone query
./ddi -q zone example.com

# Network container query
./ddi -q container 10.0.0.0/8

# DHCP queries
./ddi -q dhcp ranges
./ddi -q dhcp leases --network 10.20.30.0/24
./ddi -q dhcp failover

# Global search
./ddi -q search "server-name"
```

#### Quiet Mode Output

- **Success**: Prints absolute path to JSON file, exits 0
- **Error**: Prints JSON error to stderr, exits 1

```bash
# Success
$ ./ddi -q network 10.20.30.0/24
/Users/you/ddi-toolkit/output/network_10.20.30.0_24_20241206_143022.json

# Error
$ ./ddi -q network invalid 2>&1
{"error": "Enter valid CIDR notation", "query": "invalid"}
```

---

## Commands

### network

Query network details including DHCP pools and utilization.

```bash
./ddi -q network 10.20.30.0/24 [--view VIEW_NAME]
```

**Returns:**
- Network CIDR and comment
- Utilization (percentage, total/dynamic/static hosts)
- DHCP ranges with start/end addresses
- Active leases with MAC, hostname, expiry
- Extensible attributes
- Audit info (created, modified, by whom)

### ip

Query IP address status and bindings.

```bash
./ddi -q ip 10.20.30.50 [--view VIEW_NAME]
```

**Returns:**
- Status (USED, UNUSED, DHCP, etc.)
- Types (HOST, A, PTR, etc.)
- MAC address (if bound)
- DNS names
- Fixed address binding details
- Active lease details
- Host/A/PTR records
- Conflict status
- Audit info

### zone

Query DNS zone configuration and record counts.

```bash
./ddi -q zone example.com [--view VIEW_NAME]
```

**Returns:**
- Zone type (authoritative, forward, delegated)
- Primary and secondary DNS servers
- SOA settings
- Record counts by type (A, AAAA, CNAME, MX, etc.)
- Extensible attributes
- Audit info

### container

Query network container hierarchy.

```bash
./ddi -q container 10.0.0.0/8 [--view VIEW_NAME]
```

**Returns:**
- Container CIDR and comment
- Utilization
- Child containers (immediate children)
- Child networks (immediate children)
- Statistics (total children, total hosts)
- Audit info

### dhcp

Query DHCP ranges, leases, or failover status.

```bash
# Query all DHCP ranges
./ddi -q dhcp ranges [--network CIDR] [--view VIEW_NAME]

# Query active leases
./ddi -q dhcp leases [--network CIDR] [--view VIEW_NAME]

# Query failover associations
./ddi -q dhcp failover
```

**Returns (ranges):**
- Start/end addresses
- Associated network
- Failover association
- Utilization
- Audit info per range

**Returns (leases):**
- IP address and MAC
- Client hostname
- Lease start/end times
- Binding state
- Serving DHCP server

**Returns (failover):**
- Association name
- Primary/secondary servers
- State (normal, degraded)
- Configuration parameters
- Audit info

### search

Global search across all object types.

```bash
./ddi -q search "search-term"
```

**Searches:**
- Networks (by comment or CIDR)
- Network containers
- DNS zones
- Host records
- A records
- CNAME records
- Fixed addresses (by name or MAC)

---

## Output

All queries produce both JSON and CSV files in `./output/`:

```
output/
├── network_10.20.30.0_24_20241206_143022.json
├── network_10.20.30.0_24_20241206_143022.csv
├── ip_10.20.30.50_20241206_143145.json
└── ip_10.20.30.50_20241206_143145.csv
```

### JSON Format

```json
{
  "metadata": {
    "command": "network",
    "query": "10.20.30.0/24",
    "timestamp": "2024-12-06T14:30:22",
    "count": 1
  },
  "data": {
    "network": "10.20.30.0/24",
    "network_view": "default",
    "comment": "Production servers",
    "utilization": {
      "percentage": 45,
      "total_hosts": 254,
      "dynamic_hosts": 100,
      "static_hosts": 14
    },
    "dhcp_ranges": [...],
    "active_leases": [...],
    "audit": {
      "created": 1699574400,
      "created_by": "admin",
      "last_modified": 1701388800,
      "last_modified_by": "jsmith",
      "recent_changes": [...]
    }
  }
}
```

### CSV Format

Flattened structure suitable for spreadsheets:

```csv
network,network_view,comment,utilization.percentage,utilization.total_hosts,...
10.20.30.0/24,default,Production servers,45,254,...
```

---

## Configuration

### Config File

Settings are stored in `config.json`:

```json
{
  "version": "1.0",
  "infoblox": {
    "grid_master": "10.0.0.50",
    "username": "admin",
    "password": "BASE64_ENCODED",
    "wapi_version": "2.13.1",
    "verify_ssl": false,
    "timeout": 30
  },
  "splunk": {
    "enabled": false,
    "host": "",
    "token": "",
    "index": "",
    "sourcetype": ""
  },
  "output": {
    "default_dir": "./output",
    "timestamp_files": true
  },
  "defaults": {
    "network_view": "default",
    "dns_view": "default",
    "view_mode": "default"
  }
}
```

### Reconfigure

```bash
# Interactive
./ddi
# Press [C] for Configuration

# Or edit config.json directly
```

---

## Network View Selection

Network views provide logical separation of IP address space in InfoBlox. DDI Toolkit supports three view modes:

### View Modes

| Mode | Description |
|------|-------------|
| **default** | All queries use the configured default view |
| **all** | Queries search across all network views |
| **specific** | Select a specific view from list fetched from InfoBlox |

### Setting Network View (Interactive)

1. Press `[V]` from the main menu
2. Select view mode: default, all, or specific
3. If "specific", select from list of views fetched from WAPI

### Setting Network View (Quiet Mode)

```bash
# Use specific view
./ddi -q network 10.20.30.0/24 --view production

# Search all views (when configured)
./ddi -q ip 10.20.30.50
```

The current view mode is displayed in the main menu and at each query prompt.

---

## Audit Information

All queries include audit data:

| Field | Description |
|-------|-------------|
| `created` | Unix timestamp of object creation |
| `created_by` | Admin username who created |
| `last_modified` | Unix timestamp of last modification |
| `last_modified_by` | Admin username who last modified |
| `recent_changes` | Last 5 audit log entries |
| `splunk_audit` | Extended audit from Splunk (if enabled) |
| `fileop_audit` | Audit from WAPI fileop (fallback) |

### Audit Sources

DDI Toolkit supports two audit sources, tried in priority order:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | **Splunk** | Queries Splunk for audit logs forwarded via syslog |
| 2 | **WAPI fileop** | Downloads audit logs directly from InfoBlox |

If Splunk is configured and returns results, those are used. Otherwise, DDI Toolkit falls back to downloading audit logs directly from InfoBlox via the WAPI `fileop` function.

### WAPI Fileop Audit (Default)

When Splunk is not configured, DDI Toolkit automatically downloads audit logs from InfoBlox:

- Uses WAPI `fileop` with `get_log_files` function
- Downloads the `AUDITLOG` archive from the active grid member
- Parses audit entries and filters by object name
- Caches downloaded logs for 5 minutes to avoid repeated downloads

**Note:** InfoBlox WAPI does not expose `auditlog` as a queryable object type. The fileop method is the only way to retrieve audit data directly from InfoBlox.

### Splunk Integration (Optional)

For extended audit history and better search capabilities, configure Splunk integration:

**To enable Splunk audit integration:**

1. Ensure InfoBlox is configured to send audit logs to Splunk via syslog
2. During DDI Toolkit setup, enable Splunk integration and provide:
   - **Host:Port** - Splunk REST API endpoint (e.g., `splunk.example.com:8089`)
   - **API Token** - Bearer token with search permissions
   - **Index** - The Splunk index containing InfoBlox logs (e.g., `dhcp_idx`, `infoblox_audit`)
   - **Sourcetype** (optional) - Filter to specific log format (e.g., `syslog`, `infoblox:audit`)

**Finding your sourcetype:**
```
index="your_index" | stats count by sourcetype
```

**Note:** If sourcetype is left empty, all logs in the index are searched.

---

## Scripting Examples

### Batch Network Query

```bash
#!/bin/bash
for NET in 10.20.{30..40}.0/24; do
    echo "Querying $NET..."
    ./ddi -q network "$NET"
done
```

### Process JSON Output

```bash
#!/bin/bash
RESULT=$(./ddi -q network 10.20.30.0/24)
if [ $? -eq 0 ]; then
    # Extract utilization
    UTIL=$(cat "$RESULT" | jq '.data.utilization.percentage')
    echo "Utilization: $UTIL%"
fi
```

### Check IP Status

```bash
#!/bin/bash
check_ip() {
    RESULT=$(./ddi -q ip "$1" 2>/dev/null)
    if [ $? -eq 0 ]; then
        STATUS=$(cat "$RESULT" | jq -r '.data.status')
        echo "$1: $STATUS"
    else
        echo "$1: NOT FOUND"
    fi
}

check_ip 10.20.30.50
check_ip 10.20.30.51
```

---

## Project Structure

```
ddi-toolkit/
├── ddi                      # Main executable
├── setup.sh                 # Setup script
├── requirements.txt         # Python dependencies
├── config.json              # Configuration (generated)
├── README.md
├── QUICK_START.md
├── docs/
│   ├── PRD.md               # Product requirements
│   └── ARCHITECTURE.md      # Technical architecture
├── lib/
│   ├── config.py            # Configuration management
│   ├── wapi.py              # InfoBlox WAPI client
│   ├── audit.py             # Audit retrieval
│   ├── output.py            # Output handlers
│   ├── network_view.py      # Network view management
│   ├── ui/                  # UI components
│   └── commands/            # Query commands
├── tests/                   # Test suite
└── output/                  # Query output files
```

---

## Development

### Run Tests

```bash
source .venv/bin/activate
pip install pytest pytest-cov responses
pytest tests/ -v
```

### Add a New Command

1. Create `lib/commands/yourcommand.py`
2. Inherit from `BaseCommand`
3. Implement `execute()` method
4. Export: `command = YourCommand`

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## Troubleshooting

### "Not configured" Error

Run interactive mode to configure:
```bash
./ddi
```

### Connection Failed

1. Verify Grid Master IP/hostname
2. Check network connectivity: `ping <grid-master>`
3. Verify credentials work in GUI
4. Check WAPI is accessible: `curl -k https://<grid-master>/wapi/v2.13.1/grid`

### SSL Certificate Errors

For self-signed certificates, set `verify_ssl: false` in config.

### Permission Denied

```bash
chmod +x ./ddi ./setup.sh
```

### Import Errors

Ensure virtual environment is activated:
```bash
source .venv/bin/activate
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit pull request

---

## License

MIT License - See LICENSE file for details.

---

## Support

- Documentation: See `docs/` directory
- Issues: Report bugs via repository issues
- InfoBlox WAPI: Refer to InfoBlox documentation
