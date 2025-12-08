#!/usr/bin/env python3
"""
Live tests for DDI Toolkit quiet mode (-q/--quiet) against InfoBlox.

Uses the claude_ test data created by create_claude_test_data.py:
- Network: 10.99.1.0/24
- Container: 10.99.0.0/16
- Zone: claude-test.local
- Host: claude-server01.claude-test.local (10.99.1.10)
- A Records: claude-web01 (10.99.1.20), claude-web02 (10.99.1.21)
- CNAME: claude-www -> claude-web01
- Fixed Address: 10.99.1.50
- DHCP Range: 10.99.1.100-150

Usage:
    ./scripts/test_quiet_mode.py
"""

import subprocess
import sys
import os
import json
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test data constants (from create_claude_test_data.py)
TEST_NETWORK = "10.99.1.0/24"
TEST_CONTAINER = "10.99.0.0/16"
TEST_ZONE = "claude-test.local"
TEST_HOST = "claude-server01.claude-test.local"
TEST_IP_HOST = "10.99.1.10"
TEST_IP_A_RECORD = "10.99.1.20"
TEST_IP_FIXED = "10.99.1.50"
TEST_SEARCH_TERM = "claude"


class QuietModeTest:
    """Test runner for quiet mode commands."""

    def __init__(self):
        self.ddi_path = Path(__file__).parent.parent / "ddi"
        self.passed = 0
        self.failed = 0
        self.results = []

    def run_quiet_command(self, *args):
        """Run a ddi command in quiet mode and return (success, output_path, error)."""
        cmd = [str(self.ddi_path), "-q"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.ddi_path.parent)
        )

        if result.returncode == 0:
            output_path = result.stdout.strip()
            return True, output_path, None
        else:
            error = result.stderr.strip() if result.stderr else result.stdout.strip()
            return False, None, error

    def validate_json_output(self, output_path, required_fields=None):
        """Validate JSON output file exists and has expected structure."""
        if not output_path:
            return False, "No output path returned"

        path = Path(output_path)
        if not path.exists():
            return False, f"Output file does not exist: {output_path}"

        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

        # Check for metadata
        if "metadata" not in data:
            return False, "Missing 'metadata' field"

        if "data" not in data:
            return False, "Missing 'data' field"

        # Check required fields in data
        if required_fields:
            for field in required_fields:
                if field not in data["data"]:
                    return False, f"Missing required field: {field}"

        return True, data

    def test(self, name, args, required_fields=None, expect_error=False):
        """Run a single test."""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"Command: ddi -q {' '.join(args)}")
        print(f"{'='*60}")

        success, output_path, error = self.run_quiet_command(*args)

        if expect_error:
            if not success:
                print(f"✓ PASS - Expected error received: {error[:100] if error else 'None'}...")
                self.passed += 1
                self.results.append((name, "PASS", "Expected error"))
                return True
            else:
                print(f"✗ FAIL - Expected error but command succeeded")
                self.failed += 1
                self.results.append((name, "FAIL", "Expected error but succeeded"))
                return False

        if not success:
            print(f"✗ FAIL - Command failed: {error}")
            self.failed += 1
            self.results.append((name, "FAIL", error))
            return False

        print(f"  Output: {output_path}")

        valid, result = self.validate_json_output(output_path, required_fields)
        if not valid:
            print(f"✗ FAIL - {result}")
            self.failed += 1
            self.results.append((name, "FAIL", result))
            return False

        # Show summary of data
        data = result
        print(f"  Metadata: command={data['metadata'].get('command')}, count={data['metadata'].get('count')}")

        if isinstance(data['data'], dict):
            keys = list(data['data'].keys())[:5]
            print(f"  Data keys: {keys}...")
        elif isinstance(data['data'], list):
            print(f"  Data: {len(data['data'])} items")

        print(f"✓ PASS")
        self.passed += 1
        self.results.append((name, "PASS", output_path))
        return True

    def run_all_tests(self):
        """Run all quiet mode tests."""
        print("\n" + "=" * 60)
        print("DDI TOOLKIT - QUIET MODE LIVE TESTS")
        print("=" * 60)
        print(f"Using test data with 'claude_' prefix")
        print(f"Test Network: {TEST_NETWORK}")
        print(f"Test Zone: {TEST_ZONE}")
        print("=" * 60)

        # =====================================================================
        # NETWORK COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("NETWORK COMMAND TESTS")
        print("=" * 60)

        self.test(
            "network - basic query",
            ["network", TEST_NETWORK],
            required_fields=["network", "network_view", "utilization"]
        )

        self.test(
            "network - with view option",
            ["network", TEST_NETWORK, "--view", "default"],
            required_fields=["network"]
        )

        self.test(
            "network - invalid CIDR",
            ["network", "invalid-network"],
            expect_error=True
        )

        # =====================================================================
        # IP COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("IP COMMAND TESTS")
        print("=" * 60)

        self.test(
            "ip - host record IP",
            ["ip", TEST_IP_HOST],
            required_fields=["ip_address", "status"]
        )

        self.test(
            "ip - A record IP",
            ["ip", TEST_IP_A_RECORD],
            required_fields=["ip_address", "status"]
        )

        self.test(
            "ip - fixed address IP",
            ["ip", TEST_IP_FIXED],
            required_fields=["ip_address", "status"]
        )

        self.test(
            "ip - with view option",
            ["ip", TEST_IP_HOST, "--view", "default"],
            required_fields=["ip_address"]
        )

        self.test(
            "ip - invalid IP",
            ["ip", "not-an-ip"],
            expect_error=True
        )

        # =====================================================================
        # ZONE COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("ZONE COMMAND TESTS")
        print("=" * 60)

        self.test(
            "zone - basic query",
            ["zone", TEST_ZONE],
            required_fields=["fqdn", "view", "zone_type"]
        )

        self.test(
            "zone - with view option",
            ["zone", TEST_ZONE, "--view", "default"],
            required_fields=["fqdn"]
        )

        self.test(
            "zone - non-existent zone",
            ["zone", "nonexistent.invalid.zone"],
            expect_error=True
        )

        # =====================================================================
        # CONTAINER COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("CONTAINER COMMAND TESTS")
        print("=" * 60)

        self.test(
            "container - basic query",
            ["container", TEST_CONTAINER],
            required_fields=["network", "network_view", "hierarchy"]
        )

        self.test(
            "container - with view option",
            ["container", TEST_CONTAINER, "--view", "default"],
            required_fields=["network", "hierarchy"]
        )

        # =====================================================================
        # DHCP COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("DHCP COMMAND TESTS")
        print("=" * 60)

        self.test(
            "dhcp ranges - all ranges",
            ["dhcp", "ranges"],
            required_fields=None  # Returns list
        )

        self.test(
            "dhcp ranges - filter by network",
            ["dhcp", "ranges", "--network", TEST_NETWORK],
            required_fields=None
        )

        self.test(
            "dhcp leases - all leases",
            ["dhcp", "leases"],
            required_fields=None
        )

        self.test(
            "dhcp leases - filter by network",
            ["dhcp", "leases", "--network", TEST_NETWORK],
            required_fields=None
        )

        self.test(
            "dhcp failover - query failover",
            ["dhcp", "failover"],
            required_fields=None
        )

        # =====================================================================
        # SEARCH COMMAND TESTS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("SEARCH COMMAND TESTS")
        print("=" * 60)

        self.test(
            "search - by term 'claude'",
            ["search", TEST_SEARCH_TERM],
            required_fields=["query", "results"]
        )

        self.test(
            "search - by network CIDR",
            ["search", "10.99"],
            required_fields=["query", "results"]
        )

        self.test(
            "search - by hostname",
            ["search", "claude-server"],
            required_fields=["query", "results"]
        )

        # =====================================================================
        # EDGE CASES & OPTIONS
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("EDGE CASES & OPTION TESTS")
        print("=" * 60)

        # Test --quiet long form
        print(f"\n{'='*60}")
        print("TEST: --quiet long form option")
        print("Command: ddi --quiet network 10.99.1.0/24")
        print("=" * 60)

        cmd = [str(self.ddi_path), "--quiet", "network", TEST_NETWORK]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.ddi_path.parent))
        if result.returncode == 0 and result.stdout.strip().endswith(".json"):
            print(f"  Output: {result.stdout.strip()}")
            print("✓ PASS")
            self.passed += 1
            self.results.append(("--quiet long form", "PASS", result.stdout.strip()))
        else:
            print(f"✗ FAIL - {result.stderr or result.stdout}")
            self.failed += 1
            self.results.append(("--quiet long form", "FAIL", result.stderr or result.stdout))

        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("\n\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print("=" * 60)

        if self.failed > 0:
            print("\nFailed Tests:")
            for name, status, detail in self.results:
                if status == "FAIL":
                    print(f"  - {name}: {detail[:80]}...")

        print("\n" + "=" * 60)

        return self.failed == 0


def main():
    tester = QuietModeTest()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
