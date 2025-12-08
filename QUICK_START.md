# DDI Toolkit - Quick Start Guide

Get up and running with DDI Toolkit in 5 minutes.

---

## Prerequisites

- Python 3.8 or higher
- Network access to InfoBlox Grid Master
- InfoBlox admin credentials (read access minimum)

---

## Installation

```bash
# Clone or download the toolkit
cd /path/to/ddi-toolkit

# Run setup script
./setup.sh

# Activate virtual environment
source .venv/bin/activate
```

---

## First Run

```bash
./ddi
```

On first run, you'll be prompted to configure:

```
╔═══════════════════════════════════════════════════════════╗
║              WELCOME TO DDI TOOLKIT                       ║
╚═══════════════════════════════════════════════════════════╝

  InfoBlox Grid Master Configuration

    Example: 192.168.1.100 or gm.example.com
  Grid Master IP or Hostname: 10.0.0.50
  Admin Username [admin]: admin
  Admin Password: ********
  WAPI Version [2.13.1]: 2.13.1
  Verify SSL Certificate? [y/N]: n

  Splunk Integration (Optional)
    Splunk provides audit history: who created/modified objects

  Enable Splunk audit integration? [y/N]: y
  Splunk Host:Port: splunk.example.com:8089
  Splunk API Token: ********
  Splunk Index: dhcp_idx
  Splunk Sourcetype (optional):

  Configuration saved successfully!
```

---

## Interactive Mode

After configuration, the main menu appears:

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

  Select option: _
```

### Example: Query a Network

1. Press `1` for Query Network
2. Enter CIDR: `10.20.30.0/24`
3. Press Enter for default network view

**Output:**
```
============================================================
  Command:  network
  Query:    10.20.30.0/24
  Results:  1 record(s)
============================================================

  Summary:
    Network: 10.20.30.0/24
    Utilization: 45%
    Total Hosts: 254
    DHCP Ranges: 2
    Active Leases: 100
    Created: 2023-06-15 09:30:00
    Created By: admin
    Last Modified: 2024-12-01 14:22:00
    Modified By: jsmith

  Output Files:
    JSON: ./output/network_10.20.30.0_24_20241206_143022.json
    CSV:  ./output/network_10.20.30.0_24_20241206_143022.csv
```

---

## Quiet Mode (Scripting)

For scripts and automation, use `-q` or `--quiet`:

```bash
# Query a network
./ddi -q network 10.20.30.0/24
# Output: /full/path/to/output/network_10.20.30.0_24_20241206_143022.json

# Query an IP address
./ddi -q ip 10.20.30.50

# Query a DNS zone
./ddi -q zone example.com

# Query DHCP leases for a network
./ddi -q dhcp leases --network 10.20.30.0/24

# Global search
./ddi -q search "web-server"
```

### Using in Scripts

```bash
#!/bin/bash

# Query network and process JSON
RESULT=$(./ddi -q network 10.20.30.0/24)

if [ $? -eq 0 ]; then
    # Parse JSON output
    cat "$RESULT" | jq '.data.utilization.percentage'
else
    echo "Query failed"
fi
```

```bash
# Loop through multiple networks
for NET in 10.20.30.0/24 10.20.31.0/24 10.20.32.0/24; do
    ./ddi -q network "$NET"
done
```

---

## Common Commands

| Command | Description | Example |
|---------|-------------|---------|
| `network` | Query network details | `./ddi -q network 10.0.0.0/24` |
| `ip` | Query IP address | `./ddi -q ip 10.0.0.50` |
| `zone` | Query DNS zone | `./ddi -q zone example.com` |
| `container` | Query network container | `./ddi -q container 10.0.0.0/8` |
| `dhcp ranges` | Query DHCP pools | `./ddi -q dhcp ranges` |
| `dhcp leases` | Query active leases | `./ddi -q dhcp leases --network 10.0.0.0/24` |
| `dhcp failover` | Query failover status | `./ddi -q dhcp failover` |
| `search` | Global search | `./ddi -q search "server"` |

---

## Command Options

```bash
# Specify network view
./ddi -q network 10.20.30.0/24 --view production

# Specify DNS view
./ddi -q zone example.com --view internal

# Filter DHCP by network
./ddi -q dhcp leases --network 10.20.30.0/24
```

---

## Network View Selection

Press `[V]` from the main menu to select network view mode:

| Mode | Description |
|------|-------------|
| **default** | Use configured default view for all queries |
| **all** | Search across all network views |
| **specific** | Select a specific view from list fetched from InfoBlox |

When selecting "specific", the toolkit fetches available views from InfoBlox WAPI and presents them for selection:

```
  ═══ NETWORK VIEW SELECTION ═══

  Current Mode: default
  Current View: default

  Select View Mode
  [1] Use Default View - queries use configured default view
  [2] All Views - queries search across all network views
  [3] Specific View - select a view from InfoBlox

  Select option: 3

  Fetching network views from InfoBlox...

  Select Network View
  [1] default (default)
  [2] production - Production networks
  [3] development - Dev/test networks

  Select option: 2

  Network view settings updated!
    Mode: specific
    View: production
```

---

## Output Files

All queries produce both JSON and CSV files in `./output/`:

```
output/
├── network_10.20.30.0_24_20241206_143022.json
├── network_10.20.30.0_24_20241206_143022.csv
├── ip_10.20.30.50_20241206_143145.json
├── ip_10.20.30.50_20241206_143145.csv
└── ...
```

### JSON Structure

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
    "utilization": { ... },
    "dhcp_ranges": [ ... ],
    "audit": {
      "created": 1699574400,
      "created_by": "admin",
      "last_modified": 1701388800,
      "last_modified_by": "jsmith"
    }
  }
}
```

---

## Reconfigure

To change configuration:

**Interactive:**
```bash
./ddi
# Press [C] for Configuration
```

**Or edit directly:**
```bash
# Edit config file (be careful with JSON syntax)
nano config.json
```

---

## Test Connection

```bash
./ddi
# Press [T] for Test Connection
```

Or check connectivity manually:
```bash
curl -k -u admin:password https://your-grid-master/wapi/v2.13.1/grid
```

---

## Troubleshooting

### "Not configured" error
```bash
# Run interactive mode to configure
./ddi
```

### Connection failed
- Verify Grid Master IP/hostname
- Check network connectivity
- Verify credentials
- Check WAPI version compatibility

### SSL errors
- Set `verify_ssl: false` in config for self-signed certificates
- Or install the CA certificate

### Permission denied
```bash
chmod +x ./ddi
chmod +x ./setup.sh
```

---

## Audit Information

DDI Toolkit retrieves audit information from two sources (in priority order):

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | **Splunk** | Queries Splunk for audit logs (if configured) |
| 2 | **WAPI fileop** | Downloads audit logs directly from InfoBlox |

### Default: WAPI Fileop

Without Splunk configuration, DDI Toolkit automatically downloads audit logs from InfoBlox:

- Uses WAPI `fileop` with `get_log_files` function
- Downloads and parses the audit log archive
- Caches logs for 5 minutes to improve performance

### Optional: Splunk Integration

For extended audit history, configure Splunk:

**Prerequisites:**
- InfoBlox configured to send audit logs to Splunk via syslog
- Splunk credentials (username/password) OR API token

**Configuration fields:**
| Field | Description | Example |
|-------|-------------|---------|
| Host:Port | Splunk REST API endpoint | `splunk.example.com:8089` |
| Username | Splunk account username | `your_username` |
| Password | Splunk account password | (your password) |
| *OR* API Token | Bearer token (alternative to user/pass) | (from Splunk settings) |
| Index | Splunk index with InfoBlox logs | `dhcp_idx` |
| Sourcetype | Optional filter for log format | `syslog` or leave empty |

**Find available sourcetypes:**
```
index="your_index" | stats count by sourcetype
```

---

## Next Steps

- Read the full [README](README.md) for detailed documentation
- Check [ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details
- Review [PRD.md](docs/PRD.md) for feature specifications
