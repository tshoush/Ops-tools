# DDI Toolkit - Product Requirements Document

## Document Info
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2024-12-06 |
| Status | Implemented |
| Author | DDI Engineering Team |

---

## 1. Overview

### 1.1 Problem Statement
DDI Engineers working with InfoBlox NIOS frequently need to quickly query object details during troubleshooting, audits, and change management. The current workflow requires:
- Navigating the InfoBlox GUI (slow, requires browser)
- Writing ad-hoc WAPI calls (inconsistent, error-prone)
- Manually cross-referencing audit logs in Splunk

This results in slow incident response times and inconsistent data gathering.

### 1.2 Solution
DDI Toolkit is a command-line "Swiss Army Knife" for InfoBlox DDI Engineers that provides:
- **Interactive TUI** for guided queries with real-time feedback
- **Quiet mode** for scripting and automation
- **Unified output** in JSON and CSV formats
- **Audit integration** showing create/modify dates and admin users
- **Splunk integration** for extended audit trails

### 1.3 Target Environment
| Component | Version |
|-----------|---------|
| InfoBlox NIOS | 9.x |
| WAPI | 2.13.1 |
| Splunk | Any (optional) |
| Python | 3.8+ |

---

## 2. User Personas

### 2.1 DDI Engineer (Primary)
- **Role**: Manages DNS, DHCP, and IPAM infrastructure
- **Needs**: Quick lookups during incidents, bulk queries for audits
- **Pain Points**: Slow GUI, scattered information across systems

### 2.2 Security/Compliance Analyst
- **Role**: Audits infrastructure changes for compliance
- **Needs**: Audit trails, change history, who-did-what reports
- **Pain Points**: Manual correlation of audit logs

### 2.3 Network Operations
- **Role**: Monitors network health and capacity
- **Needs**: Utilization reports, DHCP lease status, capacity planning
- **Pain Points**: No single view of network utilization

---

## 3. Functional Requirements

### 3.1 Configuration Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | First-run wizard prompts for Grid Master, credentials | P0 |
| FR-1.2 | Store config in `config.json` with restricted permissions | P0 |
| FR-1.3 | Re-prompt with current values as defaults | P0 |
| FR-1.4 | Support Splunk integration configuration | P1 |
| FR-1.5 | Password obfuscation (base64 minimum) | P0 |
| FR-1.6 | Network View selection (default, all, or specific) | P0 |
| FR-1.7 | Fetch available views from InfoBlox WAPI | P0 |

### 3.2 Query Commands

| ID | Command | Description | Priority |
|----|---------|-------------|----------|
| FR-2.1 | `network <CIDR>` | Query network details, DHCP pools, utilization | P0 |
| FR-2.2 | `ip <address>` | Query IP status, bindings, conflicts, DNS records | P0 |
| FR-2.3 | `zone <name>` | Query DNS zone details, record counts | P0 |
| FR-2.4 | `container <CIDR>` | Query network container hierarchy | P0 |
| FR-2.5 | `dhcp ranges` | Query DHCP ranges/pools | P0 |
| FR-2.6 | `dhcp leases` | Query active DHCP leases | P0 |
| FR-2.7 | `dhcp failover` | Query DHCP failover status | P1 |
| FR-2.8 | `search <term>` | Global search across objects | P1 |

### 3.3 Audit Information

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Include create date/time for all objects | P0 |
| FR-3.2 | Include last modified date/time | P0 |
| FR-3.3 | Include admin username for create/modify | P0 |
| FR-3.4 | Show recent change history (last 5 changes) | P1 |
| FR-3.5 | Query Splunk for extended audit trail | P2 |

### 3.4 Output

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Always output both JSON and CSV files | P0 |
| FR-4.2 | Timestamped filenames by default | P1 |
| FR-4.3 | Configurable output directory | P1 |
| FR-4.4 | Console summary in interactive mode | P0 |

### 3.5 Operating Modes

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Interactive mode with TUI menu (default) | P0 |
| FR-5.2 | Quiet mode (`-q`) for scripting | P0 |
| FR-5.3 | Quiet mode outputs only file path | P0 |
| FR-5.4 | Quiet mode returns JSON errors to stderr | P0 |

### 3.6 Network View Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | Default mode: Use configured default view for all queries | P0 |
| FR-6.2 | All views mode: Search across all network views | P0 |
| FR-6.3 | Specific mode: Select from list of available views | P0 |
| FR-6.4 | Fetch views from WAPI when user selects specific mode | P0 |
| FR-6.5 | Display current view mode in main menu | P0 |
| FR-6.6 | Persist view selection in config.json | P0 |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | Single object query response time | < 5 seconds |
| NFR-1.2 | Bulk query (100 objects) | < 30 seconds |
| NFR-1.3 | Application startup time | < 2 seconds |

### 4.2 Security

| ID | Requirement |
|----|-------------|
| NFR-2.1 | Config file permissions restricted to owner (0600) |
| NFR-2.2 | No credentials in command-line arguments |
| NFR-2.3 | SSL verification configurable |
| NFR-2.4 | No secrets in output files |

### 4.3 Reliability

| ID | Requirement |
|----|-------------|
| NFR-3.1 | Graceful handling of API errors |
| NFR-3.2 | Connection timeout handling |
| NFR-3.3 | Partial results on query failures |

### 4.4 Usability

| ID | Requirement |
|----|-------------|
| NFR-4.1 | Clear error messages with remediation hints |
| NFR-4.2 | Input validation with helpful feedback |
| NFR-4.3 | Consistent command patterns |
| NFR-4.4 | Color-coded output (when TTY available) |

---

## 5. Data Model

### 5.1 Network Query Output
```json
{
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
```

### 5.2 IP Address Query Output
```json
{
  "ip_address": "10.20.30.50",
  "status": "USED",
  "types": ["HOST", "A"],
  "names": ["server1.example.com"],
  "mac_address": "00:11:22:33:44:55",
  "conflict": false,
  "bindings": {
    "fixed_address": {...},
    "lease": null
  },
  "dns_records": {
    "host_records": [...],
    "a_records": [...],
    "ptr_records": [...]
  },
  "audit": {...}
}
```

### 5.3 Zone Query Output
```json
{
  "fqdn": "example.com",
  "view": "default",
  "zone_type": "authoritative",
  "dns_servers": {
    "primary": [...],
    "secondaries": [...]
  },
  "soa": {...},
  "record_counts": {
    "A": 150,
    "AAAA": 20,
    "CNAME": 45,
    "MX": 2
  },
  "audit": {...}
}
```

---

## 6. User Interface

### 6.1 Interactive Mode Menu
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
  [C] Configuration        Grid Master, credentials
  [T] Test Connection      Verify InfoBlox connectivity
  [H] Help                 Usage and documentation
  [Q] Quit
```

### 6.2 Quiet Mode Output
```bash
$ ./ddi -q network 10.20.30.0/24
/path/to/output/network_10.20.30.0_24_20241206_143022.json

$ ./ddi -q ip 10.20.30.999
{"error": "IP 10.20.30.999 not found", "query": "10.20.30.999"}
```

---

## 7. Future Enhancements (Backlog)

| ID | Feature | Description |
|----|---------|-------------|
| BL-1 | Bulk operations | Create/modify/delete objects |
| BL-2 | Template support | Predefined query templates |
| BL-3 | Report generation | PDF/HTML reports |
| BL-4 | Scheduled queries | Cron-style scheduling |
| BL-5 | Multi-grid support | Query multiple grids |
| BL-6 | IPv6 support | Full IPv6 object queries |
| BL-7 | Discovery data | Include network discovery results |

---

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Query time reduction vs GUI | > 50% |
| Adoption rate (DDI team) | > 80% |
| Script integration | > 5 automated workflows |
| Error rate | < 1% of queries |

---

## 9. Glossary

| Term | Definition |
|------|------------|
| DDI | DNS, DHCP, IPAM |
| WAPI | Web API (InfoBlox REST API) |
| Grid Master | Primary InfoBlox management server |
| Network View | Logical separation of IP space |
| Extensible Attributes | Custom metadata fields in InfoBlox |
