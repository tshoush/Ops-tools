#!/usr/bin/env python3
"""
Create test data in InfoBlox with 'claude_' prefix for DDI Toolkit testing.

Creates:
- Network container: 10.99.0.0/16
- Network: 10.99.1.0/24
- DNS zone: claude-test.local
- Host record: claude-server01.claude-test.local
- A records: claude-web01, claude-web02
- CNAME record: claude-www
- Fixed address: 10.99.1.50
- DHCP range: 10.99.1.100-150

Usage:
    ./scripts/create_claude_test_data.py
"""

import sys
import os
import requests
import urllib3

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.config import get_infoblox_creds

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_object(base_url, auth, obj_type, data):
    """Create an object via WAPI POST."""
    url = f"{base_url}/{obj_type}"
    resp = requests.post(url, auth=auth, json=data, verify=False, timeout=30)
    if resp.status_code == 201:
        ref = resp.text.strip().strip('"')
        print(f"  Created {obj_type}: {ref}")
        return ref
    else:
        print(f"  FAILED {obj_type}: {resp.status_code} - {resp.text}")
        return None


def main():
    # Get credentials
    gm, user, pw, ver, ssl, timeout = get_infoblox_creds()
    base_url = f"https://{gm}/wapi/v{ver}"
    auth = (user, pw)

    print("=" * 60)
    print("CREATING CLAUDE TEST DATA")
    print("=" * 60)
    print(f"Grid Master: {gm}")
    print(f"WAPI Version: {ver}")
    print("=" * 60)
    print()

    created = []
    failed = []

    # 1. Create test network container
    print("1. Creating network container (10.99.0.0/16)...")
    ref = create_object(base_url, auth, "networkcontainer", {
        "network": "10.99.0.0/16",
        "network_view": "default",
        "comment": "claude_test_container - DDI Toolkit testing"
    })
    if ref:
        created.append(("container", ref))
    else:
        failed.append("container")

    # 2. Create test network
    print("\n2. Creating test network (10.99.1.0/24)...")
    ref = create_object(base_url, auth, "network", {
        "network": "10.99.1.0/24",
        "network_view": "default",
        "comment": "claude_test_network - DDI Toolkit testing",
        "options": [
            {"name": "routers", "num": 3, "value": "10.99.1.1", "vendor_class": "DHCP", "use_option": True}
        ]
    })
    if ref:
        created.append(("network", ref))
    else:
        failed.append("network")

    # 3. Create test DNS zone
    print("\n3. Creating test DNS zone (claude-test.local)...")
    ref = create_object(base_url, auth, "zone_auth", {
        "fqdn": "claude-test.local",
        "view": "default",
        "comment": "claude_test_zone - DDI Toolkit testing",
        "zone_format": "FORWARD"
    })
    if ref:
        created.append(("zone", ref))
    else:
        failed.append("zone")

    # 4. Create test host record
    print("\n4. Creating test host record (claude-server01)...")
    ref = create_object(base_url, auth, "record:host", {
        "name": "claude-server01.claude-test.local",
        "ipv4addrs": [{"ipv4addr": "10.99.1.10"}],
        "comment": "claude_test_host - DDI Toolkit testing"
    })
    if ref:
        created.append(("host", ref))
    else:
        failed.append("host")

    # 5. Create test A records
    print("\n5. Creating test A records (claude-web01, claude-web02)...")
    ref = create_object(base_url, auth, "record:a", {
        "name": "claude-web01.claude-test.local",
        "ipv4addr": "10.99.1.20",
        "comment": "claude_test_a_record - DDI Toolkit testing"
    })
    if ref:
        created.append(("a_record_1", ref))
    else:
        failed.append("a_record_1")

    ref = create_object(base_url, auth, "record:a", {
        "name": "claude-web02.claude-test.local",
        "ipv4addr": "10.99.1.21",
        "comment": "claude_test_a_record - DDI Toolkit testing"
    })
    if ref:
        created.append(("a_record_2", ref))
    else:
        failed.append("a_record_2")

    # 6. Create test CNAME record
    print("\n6. Creating test CNAME record (claude-www)...")
    ref = create_object(base_url, auth, "record:cname", {
        "name": "claude-www.claude-test.local",
        "canonical": "claude-web01.claude-test.local",
        "comment": "claude_test_cname - DDI Toolkit testing"
    })
    if ref:
        created.append(("cname", ref))
    else:
        failed.append("cname")

    # 7. Create test fixed address
    print("\n7. Creating test fixed address (10.99.1.50)...")
    ref = create_object(base_url, auth, "fixedaddress", {
        "ipv4addr": "10.99.1.50",
        "mac": "00:50:56:AA:BB:CC",
        "name": "claude_test_fixed",
        "network_view": "default",
        "comment": "claude_test_fixedaddr - DDI Toolkit testing"
    })
    if ref:
        created.append(("fixed", ref))
    else:
        failed.append("fixed")

    # 8. Create test DHCP range
    print("\n8. Creating test DHCP range (10.99.1.100-150)...")
    ref = create_object(base_url, auth, "range", {
        "start_addr": "10.99.1.100",
        "end_addr": "10.99.1.150",
        "network": "10.99.1.0/24",
        "network_view": "default",
        "comment": "claude_test_range - DDI Toolkit testing"
    })
    if ref:
        created.append(("range", ref))
    else:
        failed.append("range")

    # Summary
    print()
    print("=" * 60)
    print("CREATION SUMMARY")
    print("=" * 60)
    print(f"Created: {len(created)} objects")
    print(f"Failed:  {len(failed)} objects")
    print()
    print("Test data created:")
    print("  Container:     10.99.0.0/16")
    print("  Network:       10.99.1.0/24")
    print("  Zone:          claude-test.local")
    print("  Host:          claude-server01.claude-test.local (10.99.1.10)")
    print("  A Records:     claude-web01 (10.99.1.20), claude-web02 (10.99.1.21)")
    print("  CNAME:         claude-www -> claude-web01")
    print("  Fixed Address: 10.99.1.50 (00:50:56:AA:BB:CC)")
    print("  DHCP Range:    10.99.1.100 - 10.99.1.150")
    print()
    print("To cleanup, run: ./scripts/cleanup_claude_test_data.py")
    print("=" * 60)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
