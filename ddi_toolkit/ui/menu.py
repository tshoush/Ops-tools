"""
Main interactive menu system.
"""

import sys
from typing import Optional
from .display import (
    clear_screen, print_banner, print_status,
    print_section, print_welcome
)
from .prompts import (
    prompt_input, prompt_choice, prompt_confirm,
    validate_cidr, validate_ipv4, validate_fqdn
)
from .colors import header, success, error, warning, bold, dim, Colors
from ..config import (
    load_config, save_config, run_config_editor,
    is_configured, decode_password, get_view_settings, set_view_settings
)
from ..wapi import WAPIClient, WAPIError, reset_client
from ..network_view import (
    get_network_views, get_network_view_names,
    get_dns_views, get_dns_view_names, format_view_list,
    VIEW_MODE_DEFAULT, VIEW_MODE_ALL, VIEW_MODE_SPECIFIC
)


class MainMenu:
    """Interactive main menu."""

    def __init__(self):
        """Initialize menu with config."""
        self.config = load_config()
        self.running = True
        self.connected = False

    def show(self):
        """Display main menu and handle input loop."""
        while self.running:
            self._render_main_menu()
            choice = self._get_menu_choice()
            self._handle_choice(choice)

    def _render_main_menu(self):
        """Render the main menu screen."""
        clear_screen()
        print_banner()

        # Connection status
        ib = self.config.get("infoblox", {})
        print_status(
            ib.get("grid_master", ""),
            ib.get("username", ""),
            self.connected
        )

        # Show current view setting
        view_settings = get_view_settings()
        view_mode = view_settings.get("view_mode", "default")
        if view_mode == VIEW_MODE_ALL:
            view_display = "All Views"
        elif view_mode == VIEW_MODE_SPECIFIC:
            view_display = view_settings.get("network_view", "default")
        else:
            view_display = f"{view_settings.get('network_view', 'default')} (default)"

        print(f"  Network View: {bold(view_display)}")
        print(dim("─" * 60))

        # Menu options
        print(f"""
  {bold("QUERY COMMANDS")}

  {Colors.CYAN}[1]{Colors.RESET} Query Network        {dim("CIDR, utilization, DHCP pools")}
  {Colors.CYAN}[2]{Colors.RESET} Query IP Address     {dim("Status, bindings, conflicts")}
  {Colors.CYAN}[3]{Colors.RESET} Query DNS Zone       {dim("Zone details, record counts")}
  {Colors.CYAN}[4]{Colors.RESET} Query Container      {dim("Network containers, hierarchy")}
  {Colors.CYAN}[5]{Colors.RESET} Query DHCP           {dim("Pools, leases, failover")}
  {Colors.CYAN}[6]{Colors.RESET} Search               {dim("Global search across objects")}
  {Colors.CYAN}[7]{Colors.RESET} Bulk Operations      {dim("Create/modify/delete from file")}

  {dim("─" * 56)}

  {Colors.YELLOW}[V]{Colors.RESET} Network View        {dim("Select default, all, or specific")}
  {Colors.YELLOW}[C]{Colors.RESET} Configuration       {dim("Grid Master, credentials")}
  {Colors.YELLOW}[T]{Colors.RESET} Test Connection     {dim("Verify InfoBlox connectivity")}
  {Colors.YELLOW}[H]{Colors.RESET} Help                {dim("Usage and documentation")}
  {Colors.YELLOW}[Q]{Colors.RESET} Quit
        """)

    def _get_menu_choice(self) -> str:
        """Get menu choice from user."""
        try:
            choice = input(f"\n  {bold('Select option')}: ").strip().upper()
            return choice
        except (KeyboardInterrupt, EOFError):
            return 'Q'

    def _handle_choice(self, choice: str):
        """Handle menu selection."""
        handlers = {
            '1': self._query_network,
            '2': self._query_ip,
            '3': self._query_zone,
            '4': self._query_container,
            '5': self._query_dhcp,
            '6': self._search,
            '7': self._bulk_operations,
            'B': self._bulk_operations,
            'V': self._select_network_view,
            'C': self._configure,
            'T': self._test_connection,
            'H': self._show_help,
            'Q': self._quit,
        }

        handler = handlers.get(choice)
        if handler:
            handler()
        else:
            print(warning("\n  Invalid option. Press Enter to continue..."))
            input()

    def _ensure_configured(self) -> bool:
        """Check if InfoBlox is configured."""
        if not is_configured():
            print(error("\n  InfoBlox not configured. Please configure first (C)."))
            input("\n  Press Enter to continue...")
            return False
        return True

    def _get_effective_view(self, view_type: str = "network") -> tuple:
        """
        Get effective view based on current settings.

        Args:
            view_type: "network" or "dns"

        Returns:
            Tuple of (view_name_or_none, is_all_views)
            When is_all_views is True, view_name is None
        """
        view_settings = get_view_settings()
        view_mode = view_settings.get("view_mode", "default")

        if view_mode == VIEW_MODE_ALL:
            return (None, True)
        elif view_type == "dns":
            return (view_settings.get("dns_view", "default"), False)
        else:
            return (view_settings.get("network_view", "default"), False)

    def _run_command(self, cmd_name: str, query: str, **kwargs):
        """Run a command and display results."""
        from ..commands import get_command

        print(f"\n  {dim('Querying...')}")

        try:
            cmd_class = get_command(cmd_name)
            if not cmd_class:
                print(error(f"\n  Command '{cmd_name}' not found"))
                input("\n  Press Enter to continue...")
                return

            cmd = cmd_class()
            result = cmd.run(query, quiet=False, **kwargs)

            # Check if result is an error
            if isinstance(result, dict) and result.get("error"):
                # Check if resource was found in different views
                if result.get("found_in_views"):
                    found_views = result.get("found_in_views", [])
                    current_view = kwargs.get("network_view", "default")

                    print(warning(f"\n  {query} not found in view '{current_view}'"))
                    print(warning(f"  Found in: {', '.join(found_views)}"))

                    # Ask user if they want to query in one of those views
                    if len(found_views) == 1:
                        choice = prompt_confirm(f"\n  Query in '{found_views[0]}' instead?")
                        if choice:
                            print(f"\n  {dim('Querying...')}")
                            result = cmd.run(query, quiet=False, network_view=found_views[0], all_views=False)
                            if not result.get("error"):
                                print(success(f"\n  Query completed successfully!"))
                            else:
                                print(error(f"\n  {result.get('error')}"))
                    else:
                        print(f"\n  Select a view to query:")
                        for i, v in enumerate(found_views, 1):
                            print(f"    [{i}] {v}")
                        print(f"    [0] Cancel")

                        choice = prompt_input("Choice", default="0")
                        try:
                            idx = int(choice)
                        except ValueError:
                            idx = 0  # Invalid input, treat as cancel

                        if 1 <= idx <= len(found_views):
                            print(f"\n  {dim('Querying...')}")
                            result = cmd.run(query, quiet=False, network_view=found_views[idx-1], all_views=False)
                            if not result.get("error"):
                                print(success(f"\n  Query completed successfully!"))
                            else:
                                print(error(f"\n  {result.get('error')}"))
                else:
                    # Regular error (not found anywhere)
                    print(error(f"\n  {result.get('error')}"))
            else:
                print(success(f"\n  Query completed successfully!"))

        except WAPIError as e:
            print(error(f"\n  API Error: {e.message}"))
            if e.status_code == 401:
                self.connected = False
        except Exception as e:
            print(error(f"\n  Error: {e}"))

        input("\n  Press Enter to continue...")

    def _query_network(self):
        """Network query submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ QUERY NETWORK ═══\n"))

        # Show current view setting
        view, is_all = self._get_effective_view("network")
        if is_all:
            print(f"  {dim('View Mode: All Views')}\n")
        else:
            print(f"  {dim(f'View: {view}')}\n")

        network = prompt_input(
            "Enter Network CIDR",
            hint="Example: 10.20.30.0/24",
            validator=validate_cidr,
            error_msg="Enter valid CIDR notation (e.g., 10.0.0.0/24)"
        )

        self._run_command('network', network, network_view=view, all_views=is_all)

    def _query_ip(self):
        """IP query submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ QUERY IP ADDRESS ═══\n"))

        # Show current view setting
        view, is_all = self._get_effective_view("network")
        if is_all:
            print(f"  {dim('View Mode: All Views')}\n")
        else:
            print(f"  {dim(f'View: {view}')}\n")

        ip_addr = prompt_input(
            "Enter IP Address",
            hint="Example: 10.20.30.50",
            validator=validate_ipv4,
            error_msg="Enter valid IPv4 address"
        )

        self._run_command('ip', ip_addr, network_view=view, all_views=is_all)

    def _query_zone(self):
        """Zone query submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ QUERY DNS ZONE ═══\n"))

        # Show current view setting (DNS uses same mode)
        view, is_all = self._get_effective_view("dns")
        if is_all:
            print(f"  {dim('View Mode: All Views')}\n")
        else:
            print(f"  {dim(f'DNS View: {view}')}\n")

        zone = prompt_input(
            "Enter Zone Name",
            hint="Example: example.com",
            validator=validate_fqdn,
            error_msg="Enter valid zone name"
        )

        self._run_command('zone', zone, dns_view=view, all_views=is_all)

    def _query_container(self):
        """Container query submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ QUERY NETWORK CONTAINER ═══\n"))

        # Show current view setting
        view, is_all = self._get_effective_view("network")
        if is_all:
            print(f"  {dim('View Mode: All Views')}\n")
        else:
            print(f"  {dim(f'View: {view}')}\n")

        container = prompt_input(
            "Enter Container CIDR",
            hint="Example: 10.0.0.0/8",
            validator=validate_cidr,
            error_msg="Enter valid CIDR notation"
        )

        self._run_command('container', container, network_view=view, all_views=is_all)

    def _query_dhcp(self):
        """DHCP query submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ QUERY DHCP ═══\n"))

        # Show current view setting
        view, is_all = self._get_effective_view("network")
        if is_all:
            print(f"  {dim('View Mode: All Views')}\n")
        else:
            print(f"  {dim(f'View: {view}')}\n")

        query_type = prompt_choice(
            "Select Query Type",
            [
                ("ranges", "DHCP Ranges/Pools"),
                ("leases", "Active Leases"),
                ("failover", "Failover Status"),
            ],
            default="ranges"
        )

        network = None
        if query_type in ("ranges", "leases"):
            network = prompt_input(
                "Filter by Network (optional)",
                required=False,
                hint="Leave empty for all, or enter CIDR"
            )

        self._run_command('dhcp', query_type, network=network, network_view=view, all_views=is_all)

    def _search(self):
        """Intelligent search with auto-detection and refinement."""
        if not self._ensure_configured():
            return

        while True:
            clear_screen()
            print(header("\n  ═══ INTELLIGENT SEARCH ═══\n"))

            # Show current view setting
            view, is_all = self._get_effective_view("network")
            if is_all:
                print(f"  {dim('View Mode: All Views')}\n")
            else:
                print(f"  {dim(f'View: {view}')}\n")

            # Show type prefix hint
            print(f"  {dim('Prefixes: host: ptr: a: cname: zone: ip: mac: net: all:')}\n")

            query = prompt_input(
                "Enter search term",
                hint="e.g., server.domain.com, 10.1.2.3, host:name"
            )

            if not query:
                return

            # Run the search and get result with detection info
            result = self._run_intelligent_search(query, view, is_all)

            if result is None:
                return

            # Show refinement options
            action = self._show_search_refinement(result, query, view, is_all)

            if action == "done" or action == "back":
                return
            elif action == "new":
                continue  # Loop back for new search
            # Other actions handled in _show_search_refinement

    def _run_intelligent_search(self, query: str, view: str, is_all: bool):
        """Run intelligent search and display results."""
        from ..commands import get_command

        print(f"\n  {dim('Analyzing input...')}")

        try:
            cmd_class = get_command('search')
            if not cmd_class:
                print(error("\n  Search command not found"))
                input("\n  Press Enter to continue...")
                return None

            cmd = cmd_class()

            # First, show what type was detected (before searching)
            forced_type, clean_query = cmd._parse_type_prefix(query)
            if forced_type:
                if forced_type == "all":
                    detected_type = "Full Search (all types)"
                else:
                    detected_type = f"Explicit: {forced_type}"
            else:
                detected_type, _ = cmd._detect_input_type(clean_query)
                type_labels = {
                    "ip_address": "IP Address",
                    "cidr": "CIDR Network",
                    "mac_address": "MAC Address",
                    "fqdn": "Hostname/FQDN",
                    "zone": "Zone/Domain",
                    "text": "Generic Text"
                }
                detected_type = type_labels.get(detected_type, detected_type)

            print(f"  Detected: {bold(detected_type)}")
            print(f"  {dim('Searching...')}\n")

            result = cmd.run(query, quiet=False, network_view=view, all_views=is_all)

            if isinstance(result, dict) and result.get("error"):
                print(error(f"\n  {result.get('error')}"))
                input("\n  Press Enter to continue...")
                return None

            return result

        except Exception as e:
            print(error(f"\n  Error: {e}"))
            input("\n  Press Enter to continue...")
            return None

    def _show_search_refinement(self, result: dict, query: str, view: str, is_all: bool) -> str:
        """Show search results with refinement options."""
        data = result.get("data", result)
        stats = data.get("statistics", {})
        total = stats.get("total_results", 0)
        zone_hint = data.get("zone_hint")
        suggestions = data.get("suggestions", [])

        if total == 0:
            # No results - offer alternatives
            print(f"\n  {warning('No results found.')}\n")

            if suggestions:
                print(f"  {dim('Suggestions:')}")
                for s in suggestions:
                    print(f"    {dim(s)}")
                print()

            print(f"  {dim('[N] New search  [B] Back to menu')}\n")

            choice = input(f"  {bold('Select option')}: ").strip().upper()

            if choice == 'N':
                return "new"
            else:
                return "back"

        # Results found - show refinement options
        print()
        options = ["[Enter] Done"]

        # Add PTR option if IP was searched
        detected_type = data.get("detected_type", "")
        if detected_type == "ip_address" and "ptr_records" not in data.get("results", {}):
            options.append("[P] PTR lookup")

        # Add zone info option if FQDN was searched
        if zone_hint and detected_type == "fqdn":
            options.append(f"[Z] Zone info ({zone_hint})")

        # Always offer expand and new search
        options.append("[E] Expand search")
        options.append("[N] New search")

        print(f"  {dim('  '.join(options))}\n")

        choice = input(f"  {bold('Select option')}: ").strip().upper()

        if choice == 'P':
            # Do PTR lookup
            self._do_ptr_lookup(query, view, is_all)
            return "done"
        elif choice == 'Z' and zone_hint:
            # Zone info lookup
            self._do_zone_lookup(zone_hint, view, is_all)
            return "done"
        elif choice == 'E':
            # Expand search
            self._do_expand_search(query, view, is_all)
            return "done"
        elif choice == 'N':
            return "new"
        else:
            return "done"

    def _do_ptr_lookup(self, query: str, view: str, is_all: bool):
        """Perform PTR record lookup."""
        print(f"\n  {dim('Looking up PTR records...')}\n")
        self._run_command('search', f"ptr:{query}", network_view=view, all_views=is_all)

    def _do_zone_lookup(self, zone: str, view: str, is_all: bool):
        """Perform zone lookup."""
        print(f"\n  {dim(f'Looking up zone info for {zone}...')}\n")
        self._run_command('zone', zone, dns_view=view, all_views=is_all)

    def _do_expand_search(self, query: str, view: str, is_all: bool):
        """Expand search to all types."""
        print(f"\n  {dim('Expanding search to all types...')}\n")
        self._run_command('search', f"all:{query}", network_view=view, all_views=is_all)

    def _bulk_operations(self):
        """Bulk operations submenu for create/modify/delete."""
        if not self._ensure_configured():
            return

        from ..commands.bulk import SUPPORTED_OBJECT_TYPES

        while True:
            clear_screen()
            print(header("\n  ═══ BULK OPERATIONS ═══\n"))

            print(f"""
  {bold("⚠️  WARNING: Bulk operations modify your InfoBlox data!")}
  {dim("Always test with --dry-run first.")}

  {bold("OPERATIONS")}

  {Colors.CYAN}[1]{Colors.RESET} Bulk Create        {dim("Create objects from CSV/JSON file")}
  {Colors.CYAN}[2]{Colors.RESET} Bulk Modify        {dim("Update objects from CSV/JSON file")}
  {Colors.CYAN}[3]{Colors.RESET} Bulk Delete        {dim("Delete objects from CSV/JSON file")}

  {dim("─" * 56)}

  {Colors.YELLOW}[B]{Colors.RESET} Back to Main Menu
            """)

            choice = input(f"\n  {bold('Select option')}: ").strip().upper()

            if choice == 'B' or choice == '':
                return
            elif choice == '1':
                self._bulk_create()
            elif choice == '2':
                self._bulk_modify()
            elif choice == '3':
                self._bulk_delete()
            else:
                print(warning("\n  Invalid option."))
                input("\n  Press Enter to continue...")

    def _bulk_create(self):
        """Bulk create objects."""
        self._run_bulk_operation("create")

    def _bulk_modify(self):
        """Bulk modify objects."""
        self._run_bulk_operation("modify")

    def _bulk_delete(self):
        """Bulk delete objects."""
        self._run_bulk_operation("delete")

    def _run_bulk_operation(self, operation: str):
        """Run a bulk operation (create/modify/delete)."""
        from ..commands.bulk import SUPPORTED_OBJECT_TYPES
        from ..commands import get_command
        from pathlib import Path

        clear_screen()
        print(header(f"\n  ═══ BULK {operation.upper()} ═══\n"))

        # Show supported object types
        print(f"  {bold('Supported Object Types:')}")
        type_list = list(SUPPORTED_OBJECT_TYPES.keys())
        for i, t in enumerate(type_list):
            print(f"    {dim(f'[{i+1}]')} {t}")

        print()

        # Get object type
        type_choice = prompt_input(
            "Object Type",
            hint="e.g., network, host, a, cname, fixedaddress"
        )

        if not type_choice:
            return

        type_choice = type_choice.lower()
        if type_choice not in SUPPORTED_OBJECT_TYPES:
            # Check if it's a number
            try:
                idx = int(type_choice) - 1
                if 0 <= idx < len(type_list):
                    type_choice = type_list[idx]
                else:
                    print(error(f"\n  Invalid object type: {type_choice}"))
                    input("\n  Press Enter to continue...")
                    return
            except ValueError:
                print(error(f"\n  Unsupported object type: {type_choice}"))
                print(f"  {dim(f'Supported: {', '.join(type_list)}')}")
                input("\n  Press Enter to continue...")
                return

        # Get file path
        file_path = prompt_input(
            "Input File",
            hint="CSV or JSON file path"
        )

        if not file_path:
            return

        file_path = Path(file_path).expanduser()
        if not file_path.exists():
            print(error(f"\n  File not found: {file_path}"))
            input("\n  Press Enter to continue...")
            return

        # Dry run option
        dry_run = prompt_confirm(
            "Dry Run",
            default=True,
            hint="Preview changes without executing (recommended first)"
        )

        # Confirm if not dry run and operation is delete
        if not dry_run and operation == "delete":
            confirm = prompt_confirm(
                f"⚠️  Confirm DELETE",
                default=False,
                hint="This will permanently delete objects!"
            )
            if not confirm:
                print(f"\n  {dim('Operation cancelled.')}")
                input("\n  Press Enter to continue...")
                return

        # Execute
        print(f"\n  {dim(f'Running bulk {operation}...')}\n")

        try:
            cmd_class = get_command('bulk')
            cmd = cmd_class()
            result = cmd.run(
                operation,
                quiet=False,
                object_type=type_choice,
                file=str(file_path),
                dry_run=dry_run,
                continue_on_error=True
            )

            if result.get("error"):
                print(error(f"\n  Error: {result.get('error')}"))
                if result.get("validation_errors"):
                    print(f"\n  {bold('Validation Errors:')}")
                    for err in result.get("validation_errors", [])[:5]:
                        print(f"    - Row {err.get('index', '?')}: {err.get('error', 'Unknown')}")
            else:
                print(success(f"\n  Bulk {operation} completed!"))

        except WAPIError as e:
            print(error(f"\n  API Error: {e.message}"))
        except Exception as e:
            print(error(f"\n  Error: {e}"))

        input("\n  Press Enter to continue...")

    def _select_network_view(self):
        """Network view selection submenu."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ NETWORK VIEW SELECTION ═══\n"))

        current_settings = get_view_settings()
        current_mode = current_settings.get("view_mode", "default")
        current_view = current_settings.get("network_view", "default")

        print(f"  Current Mode: {bold(current_mode)}")
        print(f"  Current View: {bold(current_view)}\n")

        # Mode selection
        mode_choice = prompt_choice(
            "Select View Mode",
            [
                ("default", "Use Default View - queries use configured default view"),
                ("all", "All Views - queries search across all network views"),
                ("specific", "Specific View - select a view from InfoBlox"),
            ],
            default=current_mode
        )

        selected_view = current_view

        if mode_choice == "specific":
            print(f"\n  {dim('Fetching network views from InfoBlox...')}\n")

            try:
                views = get_network_views()

                if not views:
                    print(error("\n  No network views found."))
                    input("\n  Press Enter to continue...")
                    return

                # Format views for selection
                view_options = format_view_list(views)

                if not view_options:
                    print(error("\n  Could not format view list."))
                    input("\n  Press Enter to continue...")
                    return

                selected_view = prompt_choice(
                    "Select Network View",
                    view_options,
                    default=current_view if current_view in [v[0] for v in view_options] else view_options[0][0]
                )

            except WAPIError as e:
                print(error(f"\n  API Error: {e.message}"))
                print(warning("  Cannot fetch views. Using manual entry.\n"))

                selected_view = prompt_input(
                    "Enter Network View Name",
                    default=current_view
                )

            except Exception as e:
                print(error(f"\n  Error: {e}"))
                input("\n  Press Enter to continue...")
                return

        elif mode_choice == "default":
            # Allow setting the default view name
            selected_view = prompt_input(
                "Default View Name",
                default=current_view,
                hint="The view to use for all queries"
            )

        # Save settings
        dns_view = current_settings.get("dns_view", "default")
        set_view_settings(mode_choice, selected_view, dns_view)
        self.config = load_config()  # Refresh config

        print(f"\n  {success('Network view settings updated!')}")
        print(f"    Mode: {bold(mode_choice)}")
        if mode_choice != "all":
            print(f"    View: {bold(selected_view)}")

        input("\n  Press Enter to continue...")

    def _configure(self):
        """Open configuration editor."""
        self.config = run_config_editor()
        self.connected = False  # Reset connection after config change
        reset_client()

    def _test_connection(self):
        """Test InfoBlox connectivity."""
        if not self._ensure_configured():
            return

        clear_screen()
        print(header("\n  ═══ TEST CONNECTION ═══\n"))

        ib = self.config.get("infoblox", {})
        print(f"  Grid Master: {bold(ib.get('grid_master', 'N/A'))}")
        print(f"  Username:    {bold(ib.get('username', 'N/A'))}")
        print(f"  WAPI:        {bold(ib.get('wapi_version', 'N/A'))}")
        print(f"\n  {dim('Testing connection...')}\n")

        try:
            reset_client()  # Force new client
            client = WAPIClient()
            result = client.test_connection()

            self.connected = True
            print(success("  Connection successful!\n"))
            print(f"    Grid Name: {result.get('name', 'N/A')}")

        except WAPIError as e:
            self.connected = False
            print(error(f"  Connection failed: {e.message}"))

        except Exception as e:
            self.connected = False
            print(error(f"  Connection failed: {e}"))

        input("\n  Press Enter to continue...")

    def _show_help(self):
        """Show help screen."""
        clear_screen()
        print(header("\n  ═══ DDI TOOLKIT HELP ═══\n"))

        help_text = f"""
  {bold("OVERVIEW")}
  DDI Toolkit is a Swiss Army Knife for InfoBlox DDI Engineers.
  Query networks, IPs, zones, DHCP, and more from the command line.

  {bold("MODES")}

  {Colors.CYAN}Interactive (default){Colors.RESET}
    Run without arguments for this menu-driven interface.

    $ ./ddi

  {Colors.CYAN}Quiet Mode (scripting){Colors.RESET}
    Use -q or --quiet for non-interactive operation.
    Reads config from config.json, outputs file paths only.

    $ ./ddi -q network 10.20.30.0/24
    $ ./ddi -q ip 10.20.30.50
    $ ./ddi -q zone example.com
    $ ./ddi -q container 10.0.0.0/8
    $ ./ddi -q dhcp ranges --network 10.0.0.0/24
    $ ./ddi -q search "web-server"

  {Colors.CYAN}Bulk Operations{Colors.RESET}
    $ ./ddi -q bulk create network --file networks.json
    $ ./ddi -q bulk modify host --file hosts.csv --dry-run
    $ ./ddi -q bulk delete fixedaddress --file to_delete.csv

  {bold("QUIET MODE OPTIONS")}
    --view <name>      Specify network or DNS view
    --network <cidr>   Filter DHCP by network

  {bold("OUTPUT")}
  All queries generate both JSON and CSV files in ./output/
  Files are timestamped by default.

  {bold("CONFIGURATION")}
  Config is stored in config.json (auto-created on first run).
  Use option [C] to reconfigure at any time.
        """
        print(help_text)
        input("\n  Press Enter to continue...")

    def _quit(self):
        """Exit application."""
        print(f"\n  {dim('Goodbye!')}\n")
        self.running = False


def run_interactive():
    """Entry point for interactive mode."""
    try:
        menu = MainMenu()
        menu.show()
    except KeyboardInterrupt:
        print(f"\n\n  {dim('Interrupted. Goodbye!')}\n")
        sys.exit(0)
