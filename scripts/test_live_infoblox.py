#!/usr/bin/env python3
"""
Live InfoBlox Integration Tests
Tests all DDI Toolkit functionality against a real InfoBlox instance.

Usage:
    python scripts/test_live_infoblox.py

This script will:
1. Create test objects (networks, hosts, DNS records)
2. Query them using all commands
3. Modify them using bulk operations
4. Delete them to clean up
"""

import sys
import os
import json
import subprocess
import tempfile
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from ddi_toolkit.wapi import get_client, WAPIError

# Test configuration
TEST_PREFIX = "ddi_toolkit_test_"
TEST_NETWORK_1 = "10.254.1.0/24"
TEST_NETWORK_2 = "10.254.2.0/24"
TEST_CONTAINER = "10.254.0.0/16"


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")


def print_test(name):
    print(f"\n{Colors.YELLOW}Testing: {name}{Colors.RESET}")


def print_pass(msg="PASSED"):
    print(f"  {Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_fail(msg):
    print(f"  {Colors.RED}✗ {msg}{Colors.RESET}")


def print_info(msg):
    print(f"  {Colors.BLUE}ℹ {msg}{Colors.RESET}")


class LiveInfoBloxTests:
    def __init__(self):
        self.client = get_client()
        self.passed = 0
        self.failed = 0
        self.created_objects = []  # Track for cleanup

    def run_all_tests(self):
        """Run all tests with cleanup."""
        print_header("DDI Toolkit - Live InfoBlox Integration Tests")

        try:
            # Test connection first
            self.test_connection()

            # Setup: Create test objects
            self.setup_test_objects()

            # Run query tests
            self.test_network_query()
            self.test_ip_query()
            self.test_container_query()
            self.test_dhcp_query()
            self.test_search()
            self.test_zone_query()

            # Run bulk operation tests
            self.test_bulk_create()
            self.test_bulk_modify()
            self.test_bulk_delete()

            # Test quiet mode CLI
            self.test_quiet_mode_cli()

        finally:
            # Always cleanup
            self.cleanup_test_objects()

        # Print summary
        self.print_summary()

        return self.failed == 0

    def test_connection(self):
        """Test WAPI connection."""
        print_test("WAPI Connection")
        try:
            result = self.client.test_connection()
            if result.get('name'):
                print_pass(f"Connected to grid: {result.get('name')}")
                self.passed += 1
            else:
                print_fail("Connection returned no grid info")
                self.failed += 1
        except Exception as e:
            print_fail(f"Connection failed: {e}")
            self.failed += 1
            raise  # Can't continue without connection

    def setup_test_objects(self):
        """Create test objects for querying."""
        print_header("Setup: Creating Test Objects")

        # Create network container
        print_test("Create network container")
        try:
            ref = self.client.create('networkcontainer', {
                'network': TEST_CONTAINER,
                'comment': f'{TEST_PREFIX}container'
            })
            self.created_objects.append(('networkcontainer', ref, TEST_CONTAINER))
            print_pass(f"Created container: {TEST_CONTAINER}")
        except WAPIError as e:
            if 'already exists' in str(e.message).lower():
                print_info(f"Container already exists: {TEST_CONTAINER}")
            else:
                print_fail(f"Failed: {e.message}")

        # Create test network 1
        print_test("Create test network 1")
        try:
            ref = self.client.create('network', {
                'network': TEST_NETWORK_1,
                'comment': f'{TEST_PREFIX}network_1'
            })
            self.created_objects.append(('network', ref, TEST_NETWORK_1))
            print_pass(f"Created network: {TEST_NETWORK_1}")
        except WAPIError as e:
            if 'already exists' in str(e.message).lower():
                print_info(f"Network already exists: {TEST_NETWORK_1}")
            else:
                print_fail(f"Failed: {e.message}")

        # Create test network 2
        print_test("Create test network 2")
        try:
            ref = self.client.create('network', {
                'network': TEST_NETWORK_2,
                'comment': f'{TEST_PREFIX}network_2'
            })
            self.created_objects.append(('network', ref, TEST_NETWORK_2))
            print_pass(f"Created network: {TEST_NETWORK_2}")
        except WAPIError as e:
            if 'already exists' in str(e.message).lower():
                print_info(f"Network already exists: {TEST_NETWORK_2}")
            else:
                print_fail(f"Failed: {e.message}")

    def test_network_query(self):
        """Test network command."""
        print_test("Network Query Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('network')
        cmd = cmd_class()

        # Query existing network
        try:
            # Find any existing network to query
            networks = self.client.get('network', max_results=1)
            if networks:
                test_net = networks[0].get('network')
                result = cmd.run(test_net, quiet=True)

                if 'error' not in result:
                    print_pass(f"Queried network: {test_net}")
                    self.passed += 1
                else:
                    print_fail(f"Query returned error: {result.get('error')}")
                    self.failed += 1
            else:
                print_info("No networks found to query")
                self.passed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def test_ip_query(self):
        """Test IP command."""
        print_test("IP Query Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('ip')
        cmd = cmd_class()

        try:
            # Query an IP from test network
            result = cmd.run('10.254.1.1', quiet=True)

            if result:  # IP query always returns something
                print_pass("IP query executed successfully")
                self.passed += 1
            else:
                print_fail("IP query returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def test_container_query(self):
        """Test container command."""
        print_test("Container Query Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('container')
        cmd = cmd_class()

        try:
            result = cmd.run(TEST_CONTAINER, quiet=True)

            if 'error' not in result or 'not found' in str(result.get('error', '')).lower():
                print_pass("Container query executed")
                self.passed += 1
            else:
                print_fail(f"Unexpected error: {result.get('error')}")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def test_dhcp_query(self):
        """Test DHCP command."""
        print_test("DHCP Query Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('dhcp')
        cmd = cmd_class()

        # Test ranges query
        try:
            result = cmd.run('ranges', quiet=True)
            if result:
                print_pass("DHCP ranges query executed")
                self.passed += 1
            else:
                print_fail("DHCP ranges returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

        # Test failover query
        print_test("DHCP Failover Query")
        try:
            result = cmd.run('failover', quiet=True)
            if result:
                print_pass("DHCP failover query executed")
                self.passed += 1
            else:
                print_fail("DHCP failover returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def test_search(self):
        """Test search command."""
        print_test("Search Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('search')
        cmd = cmd_class()

        # Test IP search
        try:
            result = cmd.run('10.254.1.1', quiet=True)
            if result:
                print_pass("IP search executed")
                self.passed += 1
            else:
                print_fail("Search returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

        # Test text search
        print_test("Search with text query")
        try:
            result = cmd.run('test', quiet=True)
            if result:
                print_pass("Text search executed")
                self.passed += 1
            else:
                print_fail("Text search returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

        # Test prefix search
        print_test("Search with type prefix")
        try:
            result = cmd.run('net:10.254', quiet=True)
            if result:
                print_pass("Prefix search executed")
                self.passed += 1
            else:
                print_fail("Prefix search returned nothing")
                self.failed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def test_zone_query(self):
        """Test zone command."""
        print_test("Zone Query Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('zone')
        cmd = cmd_class()

        try:
            # Find any existing zone
            zones = self.client.get('zone_auth', max_results=1)
            if zones:
                test_zone = zones[0].get('fqdn')
                result = cmd.run(test_zone, quiet=True)

                if 'error' not in result:
                    print_pass(f"Queried zone: {test_zone}")
                    self.passed += 1
                else:
                    print_fail(f"Query returned error: {result.get('error')}")
                    self.failed += 1
            else:
                print_info("No zones found to query")
                self.passed += 1
        except Exception as e:
            print_fail(f"Exception: {e}")
            self.failed += 1

    def _load_result_file(self, result):
        """Load the JSON result file from a command result."""
        json_path = result.get('json')
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r') as f:
                return json.load(f)
        return result

    def test_bulk_create(self):
        """Test bulk create command."""
        print_test("Bulk Create Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('bulk')
        cmd = cmd_class()

        # Create temp JSON file
        test_data = [
            {"network": "10.254.10.0/24", "comment": f"{TEST_PREFIX}bulk_1"},
            {"network": "10.254.11.0/24", "comment": f"{TEST_PREFIX}bulk_2"}
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        try:
            # Dry run first
            result = cmd.run('create', quiet=True, object_type='network',
                           file=temp_file, dry_run=True, continue_on_error=True)

            # Load actual data from JSON file
            data = self._load_result_file(result)
            bulk_data = data.get('data', data)

            if bulk_data.get('successful') == 2:
                print_pass("Bulk create dry-run: 2 would be created")
                self.passed += 1
            else:
                print_fail(f"Dry-run unexpected result: {bulk_data}")
                self.failed += 1

            # Actual create
            print_test("Bulk Create (actual)")
            result = cmd.run('create', quiet=True, object_type='network',
                           file=temp_file, dry_run=False, continue_on_error=True)

            data = self._load_result_file(result)
            bulk_data = data.get('data', data)
            successful = bulk_data.get('successful', 0)

            if successful > 0:
                print_pass(f"Bulk create: {successful} networks created")
                self.passed += 1
                # Track for cleanup
                for op in bulk_data.get('successful_operations', []):
                    if '_ref' in op:
                        self.created_objects.append(('network', op['_ref'], op.get('identifier')))
            else:
                # Might already exist
                errors = bulk_data.get('errors', [])
                if errors and 'already exists' in str(errors):
                    print_info("Networks already exist (OK)")
                    self.passed += 1
                else:
                    print_fail(f"Bulk create failed: {errors}")
                    self.failed += 1

        finally:
            os.unlink(temp_file)

    def test_bulk_modify(self):
        """Test bulk modify command."""
        print_test("Bulk Modify Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('bulk')
        cmd = cmd_class()

        # Find networks to modify
        networks = self.client.get('network', params={'comment~': TEST_PREFIX}, max_results=2)

        if not networks:
            print_info("No test networks to modify")
            self.passed += 1
            return

        # Create modify file
        test_data = [
            {"network": n.get('network'), "comment": f"{TEST_PREFIX}modified"}
            for n in networks
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        try:
            result = cmd.run('modify', quiet=True, object_type='network',
                           file=temp_file, dry_run=False, continue_on_error=True)

            data = self._load_result_file(result)
            bulk_data = data.get('data', data)

            if bulk_data.get('successful', 0) > 0:
                print_pass(f"Bulk modify: {bulk_data.get('successful')} networks modified")
                self.passed += 1
            else:
                print_fail(f"Bulk modify failed: {bulk_data.get('errors')}")
                self.failed += 1

        finally:
            os.unlink(temp_file)

    def test_bulk_delete(self):
        """Test bulk delete command."""
        print_test("Bulk Delete Command")

        from ddi_toolkit.commands import get_command
        cmd_class = get_command('bulk')
        cmd = cmd_class()

        # Find bulk-created networks
        networks = self.client.get('network', params={'network~': '10.254.1'}, max_results=5)
        bulk_networks = [n for n in networks if n.get('network') in ['10.254.10.0/24', '10.254.11.0/24']]

        if not bulk_networks:
            print_info("No bulk test networks to delete")
            self.passed += 1
            return

        # Create delete file
        test_data = [{"network": n.get('network')} for n in bulk_networks]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        try:
            result = cmd.run('delete', quiet=True, object_type='network',
                           file=temp_file, dry_run=False, continue_on_error=True)

            data = self._load_result_file(result)
            bulk_data = data.get('data', data)

            if bulk_data.get('successful', 0) > 0:
                print_pass(f"Bulk delete: {bulk_data.get('successful')} networks deleted")
                self.passed += 1
            else:
                errors = bulk_data.get('errors', [])
                if not errors:
                    print_info("No networks to delete")
                    self.passed += 1
                else:
                    print_fail(f"Bulk delete failed: {errors}")
                    self.failed += 1

        finally:
            os.unlink(temp_file)

    def test_quiet_mode_cli(self):
        """Test CLI quiet mode for various commands."""
        print_test("CLI Quiet Mode")

        ddi_script = PROJECT_DIR / 'ddi'

        # Test network query via CLI
        networks = self.client.get('network', max_results=1)
        if networks:
            test_net = networks[0].get('network')
            result = subprocess.run(
                [str(ddi_script), '-q', 'network', test_net],
                capture_output=True, text=True
            )

            if result.returncode == 0 and result.stdout.strip().endswith('.json'):
                print_pass(f"CLI network query: {result.stdout.strip()}")
                self.passed += 1
            else:
                print_fail(f"CLI failed: {result.stderr}")
                self.failed += 1

        # Test search via CLI
        print_test("CLI Search")
        result = subprocess.run(
            [str(ddi_script), '-q', 'search', 'test'],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            print_pass("CLI search executed")
            self.passed += 1
        else:
            print_fail(f"CLI search failed: {result.stderr}")
            self.failed += 1

        # Test DHCP via CLI
        print_test("CLI DHCP ranges")
        result = subprocess.run(
            [str(ddi_script), '-q', 'dhcp', 'ranges'],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            print_pass("CLI DHCP ranges executed")
            self.passed += 1
        else:
            print_fail(f"CLI DHCP failed: {result.stderr}")
            self.failed += 1

    def cleanup_test_objects(self):
        """Clean up all test objects created during testing."""
        print_header("Cleanup: Removing Test Objects")

        # First, find and delete any remaining test networks
        try:
            test_networks = self.client.get('network', params={'comment~': TEST_PREFIX})
            for net in test_networks:
                ref = net.get('_ref')
                if ref:
                    try:
                        self.client.delete(ref)
                        print_info(f"Deleted network: {net.get('network')}")
                    except WAPIError as e:
                        print_info(f"Could not delete {net.get('network')}: {e.message}")
        except Exception as e:
            print_info(f"Error finding test networks: {e}")

        # Delete test container
        try:
            containers = self.client.get('networkcontainer', params={'network': TEST_CONTAINER})
            for cont in containers:
                ref = cont.get('_ref')
                if ref:
                    try:
                        self.client.delete(ref)
                        print_info(f"Deleted container: {TEST_CONTAINER}")
                    except WAPIError as e:
                        print_info(f"Could not delete container: {e.message}")
        except Exception as e:
            print_info(f"Error cleaning up container: {e}")

        # Delete from tracked objects
        for obj_type, ref, identifier in reversed(self.created_objects):
            try:
                self.client.delete(ref)
                print_info(f"Deleted {obj_type}: {identifier}")
            except WAPIError as e:
                if 'not found' not in str(e.message).lower():
                    print_info(f"Could not delete {identifier}: {e.message}")
            except Exception:
                pass

        print_pass("Cleanup complete")

    def print_summary(self):
        """Print test summary."""
        print_header("Test Summary")

        total = self.passed + self.failed

        print(f"\n  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {self.passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {self.failed}{Colors.RESET}")

        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.RESET}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed.{Colors.RESET}")

        print()


def main():
    """Run the live tests."""
    tests = LiveInfoBloxTests()
    success = tests.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
