#!/usr/bin/env python3
"""
DDI Toolkit - Swiss Army Knife for InfoBlox DDI Engineers

Usage:
    ./ddi                           Interactive mode (default)
    ./ddi -q <command> <query>      Quiet mode for scripting

First run will prompt for configuration.
"""

import sys
import os
import json

# Add lib to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from ddi_toolkit.config import config_exists, is_configured, run_first_time_setup, load_config


def print_quiet_error(message: str, details: dict = None):
    """Print error in JSON format for quiet mode."""
    error_obj = {"error": message}
    if details:
        error_obj.update(details)
    print(json.dumps(error_obj), file=sys.stderr)
    sys.exit(1)


def run_quiet_mode():
    """Run in quiet mode for scripting."""
    import click
    from ddi_toolkit.commands import get_command
    from ddi_toolkit.wapi import WAPIError

    @click.group()
    @click.option('--quiet', '-q', is_flag=True, hidden=True)
    def cli(quiet):
        """DDI Toolkit - Quiet mode for scripting."""
        pass

    @cli.command()
    @click.argument('query')
    @click.option('--view', default='default', help='Network view')
    def network(query, view):
        """Query network by CIDR."""
        _run_quiet_command('network', query, network_view=view)

    @cli.command()
    @click.argument('query')
    @click.option('--view', default='default', help='Network view')
    def ip(query, view):
        """Query IP address."""
        _run_quiet_command('ip', query, network_view=view)

    @cli.command()
    @click.argument('query')
    @click.option('--view', default='default', help='DNS view')
    def zone(query, view):
        """Query DNS zone."""
        _run_quiet_command('zone', query, dns_view=view)

    @cli.command()
    @click.argument('query')
    @click.option('--view', default='default', help='Network view')
    def container(query, view):
        """Query network container."""
        _run_quiet_command('container', query, network_view=view)

    @cli.command()
    @click.argument('query_type', type=click.Choice(['ranges', 'leases', 'failover']))
    @click.option('--network', default=None, help='Filter by network CIDR')
    @click.option('--view', default='default', help='Network view')
    def dhcp(query_type, network, view):
        """Query DHCP (ranges, leases, failover)."""
        _run_quiet_command('dhcp', query_type, network=network, network_view=view)

    @cli.command()
    @click.argument('query')
    @click.option('--view', default='default', help='Network view')
    def search(query, view):
        """Global search."""
        _run_quiet_command('search', query, network_view=view)

    @cli.command()
    @click.argument('operation', type=click.Choice(['create', 'modify', 'delete']))
    @click.argument('object_type')
    @click.option('--file', '-f', required=True, help='CSV or JSON file with objects')
    @click.option('--dry-run', is_flag=True, help='Preview changes without executing')
    @click.option('--stop-on-error', is_flag=True, help='Stop on first error')
    def bulk(operation, object_type, file, dry_run, stop_on_error):
        """Bulk create/modify/delete objects from file.

        Examples:
            ./ddi -q bulk create network --file networks.json
            ./ddi -q bulk modify host --file hosts.csv --dry-run
            ./ddi -q bulk delete fixedaddress --file to_delete.csv
        """
        _run_quiet_command(
            'bulk',
            operation,
            object_type=object_type,
            file=file,
            dry_run=dry_run,
            continue_on_error=not stop_on_error
        )

    def _run_quiet_command(cmd_name: str, query: str, **kwargs):
        """Execute command in quiet mode."""
        try:
            cmd_class = get_command(cmd_name)
            if not cmd_class:
                print_quiet_error(f"Unknown command: {cmd_name}")

            cmd = cmd_class()
            result = cmd.run(query, quiet=True, **kwargs)

            # Output just the JSON file path
            print(result['json'])
            sys.exit(0)

        except WAPIError as e:
            print_quiet_error(e.message, {"status_code": e.status_code})
        except Exception as e:
            print_quiet_error(str(e))

    # Remove the -q flag from args before passing to click
    args = [a for a in sys.argv[1:] if a not in ('-q', '--quiet')]
    cli(args, standalone_mode=False)


def main():
    """Main entry point."""
    # Check for quiet mode flag
    is_quiet = '-q' in sys.argv or '--quiet' in sys.argv

    if is_quiet:
        # Quiet mode: must have config
        if not config_exists() or not is_configured():
            print_quiet_error(
                "Not configured. Run './ddi' interactively first to configure.",
                {"hint": "Run ./ddi without -q to configure"}
            )

        run_quiet_mode()
    else:
        # Interactive mode
        if not config_exists():
            # First time - run setup wizard
            run_first_time_setup()

        # Show main menu
        from ddi_toolkit.ui.menu import run_interactive
        run_interactive()
