# Implementation Plan: Intelligent Search Enhancement

## Overview

Enhance the Search command with smart auto-detection and contextual refinement options.

**Behavior:**
1. User enters search term (with optional type prefix)
2. System auto-detects input type
3. System searches relevant record types automatically
4. If results found → display with option to expand/refine
5. If no results → offer alternative search types

---

## Input Detection Logic

### Detection Function: `_detect_input_type(query)`

| Pattern | Type | Regex/Logic |
|---------|------|-------------|
| `host:xxx` | Explicit Host | Prefix match |
| `ptr:xxx` | Explicit PTR | Prefix match |
| `a:xxx` | Explicit A Record | Prefix match |
| `zone:xxx` | Explicit Zone | Prefix match |
| `ip:xxx` | Explicit IP | Prefix match |
| `mac:xxx` | Explicit MAC | Prefix match |
| `x.x.x.x` | IP Address | `^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$` |
| `x.x.x.x/xx` | CIDR | `^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$` |
| `xx:xx:xx:xx:xx:xx` | MAC Address | `^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$` |
| `*.domain.tld` | Wildcard FQDN | Contains `*` and `.` |
| `host.domain.tld` | FQDN (3+ parts) | Multiple dots, looks like hostname |
| `domain.tld` | Domain/Zone | Two parts, valid TLD |
| Other | Generic Text | Fallback |

### Search Mapping by Type

| Detected Type | Primary Search | Secondary Search |
|---------------|----------------|------------------|
| IP Address | `ipv4address`, `record:host`, `record:a` | `record:ptr`, `fixedaddress` |
| CIDR | `network`, `networkcontainer` | - |
| MAC Address | `fixedaddress`, `lease` | - |
| FQDN/Hostname | `record:host`, `record:a`, `record:cname` | `record:ptr` |
| Domain/Zone | `zone_auth`, `record:host`, `record:a` | - |
| Generic Text | Full global search (all types) | - |

---

## Type Prefix Support

Users can force a specific search type using prefixes:

```
host:tarig.marriott.com    → Search record:host only
ptr:44.44.44.2             → Search record:ptr only
a:webserver.marriott.com   → Search record:a only
cname:www.marriott.com     → Search record:cname only
zone:marriott.com          → Search zone_auth only
ip:44.44.44.2              → Search ipv4address details
mac:00:50:56:aa:bb:cc      → Search fixedaddress only
mx:marriott.com            → Search record:mx only
txt:marriott.com           → Search record:txt only
srv:_ldap.marriott.com     → Search record:srv only
ns:marriott.com            → Search record:ns only
net:10.99.0.0              → Search network only
all:searchterm             → Full global search
```

---

## Interactive Mode Flow

### Happy Path (Results Found)

```
═══ INTELLIGENT SEARCH ═══

  View Mode: default

  Enter search term: tarig.marriott.com

  Detected: Hostname/FQDN
  Searching: Host Records, A Records, CNAME Records...

  ════════════════════════════════════════════════════════════
  SEARCH RESULTS: tarig.marriott.com
  ════════════════════════════════════════════════════════════

  HOST RECORDS (1)
  ────────────────────────────────────────────────────────────
    tarig.marriott.com
      IP: 44.44.44.2
      View: default
      Comment: This is a test

  ════════════════════════════════════════════════════════════
  Total: 1 result(s) found

  Output files:
    JSON: ./output/search_tarig.marriott.com_20251218_xxx.json
    CSV:  ./output/search_tarig.marriott.com_20251218_xxx.csv

  [Enter] Done  [P] PTR lookup  [E] Expand search  [N] New search
```

### No Results Path

```
═══ INTELLIGENT SEARCH ═══

  Enter search term: nonexistent.marriott.com

  Detected: Hostname/FQDN
  Searching: Host Records, A Records, CNAME Records...

  ════════════════════════════════════════════════════════════
  No results found for: nonexistent.marriott.com
  ════════════════════════════════════════════════════════════

  Try alternative searches:
    [1] PTR Records (reverse DNS)
    [2] All DNS Records (MX, TXT, SRV, NS)
    [3] Zone Search (zone details)
    [4] Full Global Search (networks, containers, fixed addr)
    [5] Enter different search term
    [B] Back to main menu

  Select option:
```

### Expand Search Option

When user presses [E] from results:

```
  Expand search to include:
    [1] PTR Records
    [2] MX Records
    [3] TXT Records
    [4] SRV Records
    [5] NS Records
    [6] Zones
    [7] Networks & Containers
    [8] Fixed Addresses
    [A] All of the above
    [B] Back to results

  Select option:
```

---

## Quiet Mode Behavior

### Default (Auto-Detect)

```bash
./ddi -q search tarig.marriott.com
```
- Auto-detects as FQDN
- Searches Host, A, CNAME records
- Returns JSON with results

### With Type Prefix

```bash
./ddi -q search host:tarig.marriott.com
./ddi -q search ptr:44.44.44.2
./ddi -q search zone:marriott.com
./ddi -q search all:marriott
```

### Error Response (No Results)

```json
{
  "metadata": {
    "command": "search",
    "query": "nonexistent.marriott.com",
    "detected_type": "fqdn",
    "search_types": ["record:host", "record:a", "record:cname"],
    "timestamp": "2025-12-18T...",
    "count": 0
  },
  "data": {
    "query": "nonexistent.marriott.com",
    "results": {},
    "statistics": {
      "total_results": 0
    },
    "suggestions": [
      "Try: ptr:nonexistent.marriott.com",
      "Try: zone:marriott.com",
      "Try: all:nonexistent.marriott.com"
    ]
  }
}
```

---

## Files to Modify/Create

### 1. `lib/commands/search.py` (Major Rewrite)

```python
class SearchCommand(BaseCommand):
    name = "search"
    description = "Intelligent search across InfoBlox objects"
    aliases = ["find", "lookup"]

    # Type prefix mapping
    TYPE_PREFIXES = {
        "host": ["record:host"],
        "ptr": ["record:ptr"],
        "a": ["record:a"],
        "cname": ["record:cname"],
        "mx": ["record:mx"],
        "txt": ["record:txt"],
        "srv": ["record:srv"],
        "ns": ["record:ns"],
        "zone": ["zone_auth"],
        "ip": ["ipv4address"],
        "mac": ["fixedaddress"],
        "net": ["network", "networkcontainer"],
        "all": None,  # Full search
    }

    def _detect_input_type(self, query: str) -> Tuple[str, str, List[str]]:
        """
        Detect input type and return search strategy.

        Returns:
            Tuple of (detected_type, clean_query, object_types_to_search)
        """
        ...

    def _search_record_type(self, obj_type: str, query: str, **kwargs) -> List[Dict]:
        """Search a specific record type."""
        ...

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute intelligent search."""
        ...
```

### 2. `lib/ui/menu.py` (Update `_search` method)

```python
def _search(self):
    """Intelligent search with auto-detection and refinement."""
    # Display search prompt with examples
    # Get input
    # Call search command
    # Display results
    # Offer refinement options if needed
    ...
```

### 3. `lib/ui/prompts.py` (Add new prompt types if needed)

- `prompt_search_refinement()` - for post-search options

### 4. `tests/test_search.py` (New test file)

- Test input detection for all types
- Test prefix parsing
- Test search execution for each type
- Test no-results handling

---

## Implementation Steps

| Step | Task | Estimated Changes |
|------|------|-------------------|
| 1 | Add `_detect_input_type()` function | ~50 lines |
| 2 | Add `_parse_type_prefix()` function | ~20 lines |
| 3 | Add individual record search methods | ~100 lines |
| 4 | Rewrite `execute()` for smart search | ~80 lines |
| 5 | Update menu `_search()` for interactive flow | ~100 lines |
| 6 | Add refinement prompts | ~50 lines |
| 7 | Update quiet mode output format | ~30 lines |
| 8 | Add tests | ~150 lines |
| 9 | Update documentation | ~50 lines |

**Total estimated: ~630 lines of changes**

---

## Record Type Details

### DNS Records to Support

| Type | WAPI Object | Key Fields | Query By |
|------|-------------|------------|----------|
| Host | `record:host` | name, ipv4addrs, view, comment, ttl | name, ipv4addr |
| A | `record:a` | name, ipv4addr, view, comment, ttl | name, ipv4addr |
| PTR | `record:ptr` | ptrdname, ipv4addr, view, comment | ptrdname, ipv4addr |
| CNAME | `record:cname` | name, canonical, view, comment | name, canonical |
| MX | `record:mx` | name, mail_exchanger, preference, view | name |
| TXT | `record:txt` | name, text, view | name |
| SRV | `record:srv` | name, target, port, priority, weight | name |
| NS | `record:ns` | name, nameserver, view | name |

### Return Fields by Type

```python
RETURN_FIELDS = {
    "record:host": ["name", "view", "ipv4addrs", "comment", "ttl", "extattrs", "zone"],
    "record:a": ["name", "view", "ipv4addr", "comment", "ttl", "extattrs", "zone"],
    "record:ptr": ["ptrdname", "view", "ipv4addr", "comment", "ttl", "extattrs", "zone"],
    "record:cname": ["name", "view", "canonical", "comment", "ttl", "extattrs", "zone"],
    "record:mx": ["name", "view", "mail_exchanger", "preference", "comment", "ttl"],
    "record:txt": ["name", "view", "text", "comment", "ttl"],
    "record:srv": ["name", "view", "target", "port", "priority", "weight", "comment"],
    "record:ns": ["name", "view", "nameserver", "comment"],
    "zone_auth": ["fqdn", "view", "comment", "zone_format"],
    "ipv4address": ["ip_address", "status", "types", "names", "network", "network_view"],
    "network": ["network", "network_view", "comment"],
    "networkcontainer": ["network", "network_view", "comment"],
    "fixedaddress": ["ipv4addr", "mac", "name", "network_view", "comment"],
}
```

---

## Open Questions - RESOLVED

1. **PTR auto-lookup**: When searching an IP, should we automatically do reverse DNS lookup and show PTR record?
   - **ANSWER: YES** - Automatically include PTR lookup when searching by IP

2. **Zone context**: When searching `host.zone.com`, should we also show zone info for `zone.com`?
   - **ANSWER: Show host first, then offer zone info** - Display host results, then offer `[Z] View Zone Info` option

3. **Result limits**: Keep 25 per type, or adjust based on search type?
   - **ANSWER: YES** - Keep 25 per type

4. **Wildcard support**: Should `web*` automatically become `web*` regex search?
   - **ANSWER: YES** - Auto-convert wildcards to regex patterns

---

## Approval Checklist

- [x] Input detection logic approved
- [x] Type prefix syntax approved
- [x] Interactive flow approved
- [x] Quiet mode output format approved
- [x] Record types to support approved
- [x] PTR auto-lookup for IP searches approved
- [x] Zone info as post-result option approved
- [x] Wildcard auto-conversion approved
- [x] Ready to implement

---

## Next Steps

Once approved:
1. Implement `_detect_input_type()` and `_parse_type_prefix()`
2. Add individual record search methods
3. Update `execute()` method
4. Update interactive menu flow
5. Add tests
6. Test against live InfoBlox
7. Update documentation
