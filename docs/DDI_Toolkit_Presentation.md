---
marp: true
theme: default
paginate: true
backgroundColor: #ffffff
color: #1a1a1a
style: |
  :root {
    --marriott-red: #b41f3a;
    --marriott-dark: #1a1a1a;
    --marriott-gray: #5b5e5e;
    --marriott-light: #f5f5f5;
  }
  section {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  }
  h1 {
    color: var(--marriott-red);
    border-bottom: 3px solid var(--marriott-red);
    padding-bottom: 10px;
  }
  h2 {
    color: var(--marriott-dark);
  }
  a {
    color: var(--marriott-red);
  }
  code {
    background-color: var(--marriott-light);
    color: var(--marriott-dark);
    padding: 2px 8px;
    border-radius: 4px;
  }
  pre {
    background-color: #2d2d2d;
    border-left: 4px solid var(--marriott-red);
  }
  table {
    font-size: 0.85em;
  }
  th {
    background-color: var(--marriott-red);
    color: white;
  }
  footer {
    color: var(--marriott-gray);
  }
  section.title {
    background: linear-gradient(135deg, var(--marriott-red) 0%, #8a1830 100%);
    color: white;
  }
  section.title h1 {
    color: white;
    border-bottom: 3px solid white;
    font-size: 2.5em;
  }
  section.title h2 {
    color: rgba(255,255,255,0.9);
  }
  .highlight {
    color: var(--marriott-red);
    font-weight: bold;
  }
---

<!-- _class: title -->

# DDI Toolkit

## Swiss Army Knife for InfoBlox Engineers

**Marriott DDI Team**
WAPI v2.13.1

---

# Agenda

1. **Problem Statement** - Current challenges
2. **Solution Overview** - What DDI Toolkit provides
3. **Key Features** - Capabilities at a glance
4. **Architecture** - How it works
5. **Demo** - Live walkthrough
6. **Getting Started** - Quick setup guide

---

# The Problem

### Current DDI Query Workflow

| Challenge | Impact |
|-----------|--------|
| **GUI Navigation** | Slow, requires browser, multiple clicks |
| **Ad-hoc WAPI Calls** | Inconsistent, error-prone, no standards |
| **Audit Trail** | Manual cross-referencing with Splunk |
| **Output Formats** | Copy/paste into spreadsheets |
| **Network Views** | Easy to query wrong view |

### Result
- Slow incident response times
- Inconsistent data gathering
- No audit trail in query results

---

# The Solution

## DDI Toolkit

A **command-line tool** that provides:

- **Instant queries** - Network, IP, Zone, DHCP in seconds
- **Audit trail included** - Who created/modified, when
- **Multiple output formats** - JSON + CSV automatically
- **Network View aware** - Default, all, or specific views
- **Two modes** - Interactive TUI or quiet scripting

---

# Key Features

| Feature | Description |
|---------|-------------|
| **Interactive TUI** | Menu-driven interface with guided prompts |
| **Quiet Mode** | `-q` flag for scripting and automation |
| **Network Views** | Query default, all, or specific views |
| **Full Audit Trail** | Create/modify dates and admin users |
| **Splunk Integration** | Extended audit history (optional) |
| **Dual Output** | JSON and CSV for every query |
| **Large Dataset Support** | Paging and streaming for huge results |

---

# Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `network` | CIDR, utilization, DHCP pools | `10.20.30.0/24` |
| `ip` | Status, bindings, conflicts, DNS | `10.20.30.50` |
| `zone` | DNS zone details, record counts | `example.com` |
| `container` | Network container hierarchy | `10.0.0.0/8` |
| `dhcp` | Ranges, leases, failover status | `ranges`, `leases` |
| `search` | Global search across objects | `"web-server"` |

---

# Interactive Mode

```
╔════════════════════════════════════════════╗
║       DDI Toolkit - Marriott DDI Team      ║
║              WAPI v2.13.1                  ║
╚════════════════════════════════════════════╝
  Grid Master: gm.marriott.com  |  Status: ● Connected
  Network View: default (default)

  QUERY COMMANDS
  [1] Query Network        [2] Query IP Address
  [3] Query DNS Zone       [4] Query Container
  [5] Query DHCP           [6] Search

  [V] Network View    [C] Configuration
  [T] Test Connection [H] Help  [Q] Quit
```

---

# Quiet Mode (Scripting)

### Single Queries
```bash
./ddi -q network 10.20.30.0/24
./ddi -q ip 10.20.30.50
./ddi -q zone example.marriott.com
```

### Batch Processing
```bash
for NET in 10.20.{30..40}.0/24; do
    ./ddi -q network "$NET"
done
```

### Output
```
/path/to/output/network_10.20.30.0_24_20241206_143022.json
```

---

# Network View Support

### Three Modes

| Mode | Behavior |
|------|----------|
| **Default** | All queries use configured default view |
| **All Views** | Search across ALL network views |
| **Specific** | Select from list fetched from InfoBlox |

### Selection
- Press `[V]` from main menu
- Views are fetched live from WAPI
- Setting persists in config

---

# Audit Information

Every query includes:

```json
{
  "audit": {
    "created": "2023-06-15 09:30:00",
    "created_by": "admin",
    "last_modified": "2024-12-01 14:22:00",
    "last_modified_by": "jsmith",
    "recent_changes": [...]
  }
}
```

### Data Sources
- **WAPI Audit Log** - Native InfoBlox audit
- **Splunk** - Extended history (optional)

---

# Output Formats

### Automatic Dual Output

Every query generates both:

| Format | Use Case |
|--------|----------|
| **JSON** | Automation, APIs, detailed data |
| **CSV** | Excel, reporting, quick analysis |

### File Location
```
output/
├── network_10.20.30.0_24_20241206_143022.json
├── network_10.20.30.0_24_20241206_143022.csv
└── ...
```

---

# Architecture

```
┌─────────────────────────────────────────────┐
│              DDI Toolkit                     │
├─────────────────────────────────────────────┤
│   CLI (ddi)  →  Interactive / Quiet Mode    │
├─────────────────────────────────────────────┤
│   Commands: network | ip | zone | dhcp | ...│
├─────────────────────────────────────────────┤
│   Core: WAPI Client | Audit | Output        │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   InfoBlox    Splunk     File System
     WAPI      (opt)       (output)
```

---

# Performance Optimizations

### Large Dataset Handling

| Feature | Benefit |
|---------|---------|
| **WAPI Paging** | Fetches 1000 records per page |
| **Streaming Output** | Writes directly to files |
| **Memory Efficient** | Never loads all data in memory |
| **Batch Processing** | Groups I/O operations |

### Thresholds
- Auto-streams datasets > 5,000 records
- Configurable page size

---

# Getting Started

### 1. Clone & Setup
```bash
git clone https://github.com/tshoush/Ops-tools.git
cd Ops-tools
./setup.sh
source .venv/bin/activate
```

### 2. First Run
```bash
./ddi
```
Configure: Grid Master, credentials, WAPI version

### 3. Start Querying!

---

# Configuration

### Stored in `config.json`

```json
{
  "infoblox": {
    "grid_master": "gm.marriott.com",
    "username": "admin",
    "wapi_version": "2.13.1"
  },
  "defaults": {
    "network_view": "default",
    "view_mode": "default"
  }
}
```

- Passwords base64 encoded
- File permissions restricted (0600)

---

# Security

| Aspect | Implementation |
|--------|----------------|
| **Credential Storage** | Base64 obfuscation, restricted permissions |
| **No CLI Credentials** | Never passed as arguments |
| **SSL Configurable** | Support for self-signed certs |
| **Output Security** | No credentials in output files |

### Recommendations
- Use service account with read-only access
- Consider keyring integration for production

---

# Use Cases

### Incident Response
- Quick IP lookup during outages
- Verify DNS records instantly
- Check DHCP lease status

### Audits & Compliance
- Who created this network?
- When was this zone modified?
- Export data for reports

### Automation
- Batch network inventory
- Scheduled capacity reports
- Integration with monitoring

---

# Extensibility

### Adding New Commands

1. Create `lib/commands/newcmd.py`
2. Inherit from `BaseCommand`
3. Implement `execute()` method
4. Auto-discovered on next run

### Plugin Architecture
```python
class MyCommand(BaseCommand):
    name = "mycommand"
    description = "Does something"

    def execute(self, query, **kwargs):
        # Your logic here
        return {"result": data}
```

---

# Summary

### DDI Toolkit Benefits

| Before | After |
|--------|-------|
| GUI clicks, slow | Instant CLI queries |
| Manual audit lookup | Audit included automatically |
| Copy/paste to Excel | JSON + CSV auto-generated |
| Wrong network view | View-aware queries |
| Ad-hoc scripts | Standardized tool |

---

<!-- _class: title -->

# Questions?

## Resources

- **GitHub**: github.com/tshoush/Ops-tools
- **Docs**: README.md, QUICK_START.md
- **Architecture**: docs/ARCHITECTURE.md

**Marriott DDI Team**

---

# Appendix: Sample Output

### Network Query Result

```json
{
  "network": "10.20.30.0/24",
  "network_view": "default",
  "utilization": {
    "percentage": 45,
    "total_hosts": 254
  },
  "dhcp_ranges": 2,
  "active_leases": 100,
  "audit": {
    "created_by": "admin",
    "last_modified_by": "jsmith"
  }
}
```
