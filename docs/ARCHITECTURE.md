# DDI Toolkit - Architecture Document

## Document Info
| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2024-12-06 |
| Status | Implemented |

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DDI Toolkit                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    CLI      │  │  Interactive│  │     Quiet Mode          │  │
│  │  (ddi)      │──│    Menu     │  │     (Scripting)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                │                    │                  │
│         └────────────────┼────────────────────┘                  │
│                          │                                       │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │                    Command Layer                           │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │  │
│  │  │ network │ │   ip    │ │  zone   │ │container│ ...      │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │                    Core Services                           │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │  │
│  │  │  WAPI   │ │  Audit  │ │ Output  │ │ Config  │          │  │
│  │  │ Client  │ │ Client  │ │ Writer  │ │ Manager │          │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  InfoBlox   │ │   Splunk    │ │ File System │
    │    WAPI     │ │  REST API   │ │  (Output)   │
    └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 2. Directory Structure

```
ddi-toolkit/
├── ddi                          # Main entry point (executable)
├── setup.sh                     # Bootstrap script
├── requirements.txt             # Python dependencies
├── config.json                  # Runtime config (generated, gitignored)
├── .gitignore
│
├── docs/                        # Documentation
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── QUICK_START.md
│   └── README.md
│
├── lib/                         # Core library
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── wapi.py                  # InfoBlox WAPI client
│   ├── audit.py                 # Audit data retrieval
│   ├── output.py                # JSON/CSV output handlers
│   ├── network_view.py          # Network view management
│   │
│   ├── ui/                      # User interface components
│   │   ├── __init__.py
│   │   ├── colors.py            # Terminal colors/styling
│   │   ├── display.py           # Banner, status, helpers
│   │   ├── prompts.py           # Input prompts with validation
│   │   └── menu.py              # Interactive main menu
│   │
│   └── commands/                # Command modules (plugin pattern)
│       ├── __init__.py          # Command registry
│       ├── base.py              # Base command class
│       ├── network.py           # Network queries
│       ├── ip.py                # IP address queries
│       ├── zone.py              # DNS zone queries
│       ├── container.py         # Network container queries
│       ├── dhcp.py              # DHCP queries
│       └── search.py            # Global search
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_config.py
│   ├── test_wapi.py
│   ├── test_commands.py
│   └── test_output.py
│
└── output/                      # Query output files (gitignored)
    ├── *.json
    └── *.csv
```

---

## 3. Component Details

### 3.1 Entry Point (`ddi`)

**Responsibilities:**
- Parse command-line arguments
- Detect operating mode (interactive vs quiet)
- Bootstrap configuration on first run
- Route to appropriate handler

**Flow:**
```
┌─────────────────────────────────────────────────────────┐
│                         ddi                              │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ config.json     │
                  │ exists?         │
                  └─────────────────┘
                    │           │
                   NO          YES
                    │           │
                    ▼           ▼
          ┌──────────────┐  ┌──────────────┐
          │ First-time   │  │ Check -q     │
          │ Setup Wizard │  │ flag         │
          └──────────────┘  └──────────────┘
                    │           │        │
                    │          YES      NO
                    │           │        │
                    ▼           ▼        ▼
          ┌──────────────┐  ┌──────────────┐
          │ Interactive  │  │ Quiet Mode   │
          │ Menu         │  │ Execute Cmd  │
          └──────────────┘  └──────────────┘
```

### 3.2 Configuration Manager (`lib/config.py`)

**Responsibilities:**
- Load/save `config.json`
- First-time setup wizard
- Configuration editor with defaults
- Password encoding/decoding
- Credential retrieval for WAPI client

**Key Functions:**
```python
config_exists() -> bool
load_config() -> Dict
save_config(config: Dict) -> None
is_configured() -> bool
run_first_time_setup() -> Dict
run_config_editor() -> Dict
get_infoblox_creds() -> Tuple
encode_password(password: str) -> str
decode_password(encoded: str) -> str
```

**Config Schema:**
```json
{
  "version": "1.0",
  "infoblox": {
    "grid_master": "string",
    "username": "string",
    "password": "string (base64)",
    "wapi_version": "string",
    "verify_ssl": "boolean",
    "timeout": "integer"
  },
  "splunk": {
    "enabled": "boolean",
    "host": "string",
    "token": "string",
    "index": "string"
  },
  "output": {
    "default_dir": "string",
    "timestamp_files": "boolean"
  },
  "defaults": {
    "network_view": "string",
    "dns_view": "string",
    "view_mode": "string"  // "default", "all", or "specific"
  }
}
```

### 3.3 Network View Manager (`lib/network_view.py`)

**Responsibilities:**
- Fetch network views from InfoBlox WAPI
- Fetch DNS views from InfoBlox WAPI
- Resolve effective view for queries based on mode
- Format views for display in selection menu

**Key Functions:**
```python
# Constants
VIEW_MODE_DEFAULT = "default"   # Use configured default view
VIEW_MODE_ALL = "all"           # Query all network views
VIEW_MODE_SPECIFIC = "specific" # Use a specific selected view

# Functions
get_network_views() -> List[Dict]       # Fetch all network views
get_network_view_names() -> List[str]   # Get view name list
get_default_network_view() -> str       # Get default view name
get_dns_views() -> List[Dict]           # Fetch all DNS views
get_dns_view_names() -> List[str]       # Get DNS view name list
resolve_view_for_query(view_mode, selected_view, default) -> Optional[str]
format_view_list(views) -> List[tuple]  # Format for menu
```

**View Mode Behavior:**
| Mode | Behavior |
|------|----------|
| default | All queries filtered by configured default view |
| all | Queries return results from all network views |
| specific | Queries filtered by user-selected view |

### 3.4 WAPI Client (`lib/wapi.py`)

**Responsibilities:**
- REST API communication with InfoBlox
- Connection management with session reuse
- Error handling and retries
- Response parsing

**Key Classes:**
```python
class WAPIError(Exception):
    message: str
    status_code: int
    response: dict

class WAPIClient:
    def get(object_type, params, return_fields, max_results) -> List[Dict]
    def get_by_ref(ref, return_fields) -> Dict
    def search(search_string, object_types, max_results) -> List[Dict]
    def test_connection() -> Dict
```

**Singleton Pattern:**
```python
_client: Optional[WAPIClient] = None

def get_client() -> WAPIClient
def reset_client() -> None  # After config changes
```

### 3.4 Audit Client (`lib/audit.py`)

**Responsibilities:**
- Query InfoBlox auditlog for change history
- Query Splunk for extended audit trail
- Format timestamps for display
- Extract create/modify metadata

**Key Functions:**
```python
class AuditClient:
    def get_object_audit(object_ref, object_type, object_name, max_results) -> Dict
    def _get_wapi_audit(object_ref, object_type, max_results) -> List[Dict]
    def _get_splunk_audit(object_name, object_type, max_results) -> List[Dict]

def get_audit_for_object(...) -> Dict  # Convenience function
def format_audit_summary(audit_info) -> Dict  # For display
```

**Audit Data Structure:**
```json
{
  "wapi_audit": [
    {
      "timestamp": 1701388800,
      "timestamp_formatted": "2024-12-01 10:00:00",
      "admin": "jsmith",
      "action": "UPDATE",
      "object_type": "NETWORK",
      "object_name": "10.20.30.0/24",
      "message": "Modified DHCP options"
    }
  ],
  "timestamps": {
    "created": 1699574400,
    "last_modified": 1701388800
  },
  "created_by": "admin",
  "last_modified_by": "jsmith",
  "splunk_audit": [...]
}
```

### 3.5 Output Writer (`lib/output.py`)

**Responsibilities:**
- Generate JSON output with metadata
- Generate CSV output (flattened)
- Manage output directory and filenames
- Console output in interactive mode

**Key Classes:**
```python
class OutputWriter:
    def __init__(command_name, query, quiet)
    def write(data, summary) -> Dict[str, str]  # Returns file paths

def flatten_dict(d, parent_key, sep) -> Dict  # For CSV
def write_output(...) -> Dict[str, str]  # Convenience function
```

**Output JSON Structure:**
```json
{
  "metadata": {
    "command": "network",
    "query": "10.20.30.0/24",
    "timestamp": "2024-12-06T14:30:22",
    "count": 1
  },
  "data": { ... }
}
```

### 3.6 Command Layer (`lib/commands/`)

**Plugin Architecture:**
Commands are auto-discovered at runtime. To add a new command:

1. Create `lib/commands/<name>.py`
2. Inherit from `BaseCommand`
3. Implement `execute()` method
4. Export as `command = YourCommand`

**Base Command:**
```python
class BaseCommand(ABC):
    name: str = "base"
    description: str = "Description"
    aliases: List[str] = []

    @abstractmethod
    def execute(self, query: str, **kwargs) -> Dict[str, Any]

    def run(self, query: str, quiet: bool, **kwargs) -> Dict[str, str]
```

**Command Registry:**
```python
def get_command(name: str) -> Optional[Type[BaseCommand]]
def list_commands() -> Dict[str, str]
def get_command_names() -> List[str]
```

### 3.7 UI Components (`lib/ui/`)

**Colors (`colors.py`):**
- TTY detection for graceful fallback
- ANSI color codes
- Style helper functions

**Display (`display.py`):**
- `clear_screen()` - Clear terminal
- `print_banner()` - Application banner
- `print_status()` - Connection status bar
- `print_welcome()` - First-time welcome

**Prompts (`prompts.py`):**
- `prompt_input()` - Text input with defaults
- `prompt_choice()` - Multiple choice selection
- `prompt_confirm()` - Yes/no confirmation
- Validators: `validate_ip`, `validate_cidr`, `validate_fqdn`

**Menu (`menu.py`):**
- `MainMenu` class with state management
- Command routing
- Connection status tracking

---

## 4. Data Flow

### 4.1 Interactive Query Flow

```
User Input → Menu → Command → WAPI Client → InfoBlox
                                    │
                              Audit Client → InfoBlox/Splunk
                                    │
                              Output Writer → JSON/CSV Files
                                    │
                              Console Summary → User
```

### 4.2 Quiet Mode Query Flow

```
CLI Args → Argument Parser → Command → WAPI Client → InfoBlox
                                 │
                           Audit Client → InfoBlox/Splunk
                                 │
                           Output Writer → JSON/CSV Files
                                 │
                           Print JSON Path → stdout
                           (or Error → stderr)
```

---

## 5. Error Handling

### 5.1 Error Categories

| Category | Handling |
|----------|----------|
| Config missing | Redirect to setup wizard (interactive) or error (quiet) |
| Connection error | Display error, offer retry (interactive) or exit 1 (quiet) |
| Auth failure | Clear error message, suggest config check |
| Object not found | Return empty result with error field |
| API error | Include status code and message |
| Timeout | Configurable timeout, clear message |

### 5.2 Error Response (Quiet Mode)

```json
{
  "error": "Connection failed: Connection refused",
  "query": "10.20.30.0/24",
  "hint": "Check Grid Master IP and network connectivity"
}
```

---

## 6. Security Considerations

### 6.1 Credential Storage

- Passwords stored with base64 encoding (obfuscation, not encryption)
- Config file permissions set to `0600` (owner read/write only)
- For production environments, recommend:
  - Using OS keyring (`keyring` library)
  - Environment variables
  - HashiCorp Vault integration

### 6.2 Network Security

- SSL verification configurable (default: disabled for self-signed certs)
- No credentials passed via command-line arguments
- Session tokens not logged

### 6.3 Output Security

- No credentials in output files
- Audit data may contain admin usernames (expected behavior)

---

## 7. Performance Considerations

### 7.1 Optimizations

- WAPI client uses session pooling for connection reuse
- Singleton pattern prevents redundant client initialization
- Audit queries limited to prevent excessive API calls
- Lazy loading of components

### 7.2 Bottlenecks

- DHCP lease queries can be slow for large networks
- Record counting for zones with many records
- Splunk queries depend on network latency

### 7.3 Recommendations

- Use network filters for DHCP queries
- Consider caching for repeated queries (future enhancement)
- Parallel command execution for bulk operations (future)

---

## 8. Testing Strategy

### 8.1 Test Categories

| Category | Description |
|----------|-------------|
| Unit Tests | Individual function testing with mocks |
| Integration Tests | WAPI client with mock server |
| End-to-End Tests | Full command execution |

### 8.2 Mock Strategy

- Mock `WAPIClient` for command tests
- Mock `requests` for WAPI client tests
- Use fixtures for common test data

### 8.3 Test Coverage Targets

- Core modules: > 80%
- Commands: > 70%
- UI components: > 50%

---

## 9. Extension Points

### 9.1 Adding New Commands

1. Create `lib/commands/newcmd.py`
2. Inherit from `BaseCommand`
3. Implement `execute()` method
4. Set `name`, `description`, `aliases`
5. Export: `command = NewCommand`
6. Command auto-registers on next run

### 9.2 Adding New Output Formats

1. Extend `OutputWriter` class
2. Add format method (e.g., `_write_xml()`)
3. Update `write()` to call new format

### 9.3 Adding Authentication Methods

1. Extend `config.py` with new credential type
2. Update `WAPIClient.__init__` to handle new auth
3. Update setup wizard for new options

---

## 10. Dependencies

### 10.1 Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| requests | >= 2.31.0 | HTTP client for WAPI |
| urllib3 | >= 2.0.0 | HTTP library |
| rich | >= 13.7.0 | Terminal formatting |
| click | >= 8.1.0 | CLI framework |

### 10.2 Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >= 7.0.0 | Test framework |
| pytest-cov | >= 4.0.0 | Coverage reporting |
| responses | >= 0.23.0 | HTTP mocking |
