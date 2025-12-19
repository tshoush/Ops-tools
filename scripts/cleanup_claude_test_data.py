#!/usr/bin/env python3
"""
Cleanup script for claude_ test data in InfoBlox.

This script removes all test objects created with the 'claude_' prefix:
- DNS records (host, A, CNAME)
- Fixed addresses
- DHCP ranges
- Networks
- Network containers
- DNS zones

Usage:
    ./scripts/cleanup_claude_test_data.py [--dry-run]

Options:
    --dry-run    Show what would be deleted without actually deleting
"""

import sys
import os
import argparse
import requests
import urllib3

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ddi_toolkit.config import get_infoblox_creds

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_objects_by_comment(base_url, auth, obj_type, search_field="comment", search_term="claude_"):
    """Find objects with claude_ in the specified field."""
    url = f"{base_url}/{obj_type}"
    params = {
        f"{search_field}~": search_term,
        "_return_fields": f"{search_field}",
        "_max_results": 1000
    }

    try:
        resp = requests.get(url, auth=auth, params=params, verify=False, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"  Error querying {obj_type}: {e}")
        return []


def get_objects_by_name(base_url, auth, obj_type, search_term="claude"):
    """Find objects with claude in the name field."""
    url = f"{base_url}/{obj_type}"
    params = {
        "name~": search_term,
        "_return_fields": "name",
        "_max_results": 1000
    }

    try:
        resp = requests.get(url, auth=auth, params=params, verify=False, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"  Error querying {obj_type}: {e}")
        return []


def get_objects_by_fqdn(base_url, auth, obj_type, search_term="claude"):
    """Find zones with claude in the fqdn."""
    url = f"{base_url}/{obj_type}"
    params = {
        "fqdn~": search_term,
        "_return_fields": "fqdn",
        "_max_results": 1000
    }

    try:
        resp = requests.get(url, auth=auth, params=params, verify=False, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"  Error querying {obj_type}: {e}")
        return []


def delete_object(base_url, auth, obj_ref, dry_run=False):
    """Delete an object by its _ref."""
    if dry_run:
        print(f"  [DRY-RUN] Would delete: {obj_ref}")
        return True

    url = f"{base_url}/{obj_ref}"
    try:
        resp = requests.delete(url, auth=auth, verify=False, timeout=30)
        if resp.status_code == 200:
            print(f"  Deleted: {obj_ref}")
            return True
        else:
            print(f"  Failed to delete {obj_ref}: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"  Error deleting {obj_ref}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Cleanup claude_ test data from InfoBlox")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    # Get credentials
    gm, user, pw, ver, ssl, timeout = get_infoblox_creds()
    base_url = f"https://{gm}/wapi/v{ver}"
    auth = (user, pw)

    print("=" * 60)
    print("CLAUDE TEST DATA CLEANUP")
    print("=" * 60)
    print(f"Grid Master: {gm}")
    print(f"WAPI Version: {ver}")
    if args.dry_run:
        print("MODE: DRY-RUN (no changes will be made)")
    print("=" * 60)
    print()

    deleted_count = 0
    failed_count = 0

    # Order matters - delete dependent objects first
    # 1. Delete DNS records first (they depend on zones)
    print("1. Finding and deleting DNS records...")

    for obj_type in ["record:host", "record:a", "record:cname", "record:ptr", "record:mx", "record:txt"]:
        objects = get_objects_by_name(base_url, auth, obj_type, "claude")
        if objects:
            print(f"   Found {len(objects)} {obj_type} records")
            for obj in objects:
                if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                    deleted_count += 1
                else:
                    failed_count += 1

    # 2. Delete fixed addresses
    print("\n2. Finding and deleting fixed addresses...")
    fixed_addrs = get_objects_by_comment(base_url, auth, "fixedaddress", "comment", "claude_")
    fixed_addrs += get_objects_by_name(base_url, auth, "fixedaddress", "claude")

    # Deduplicate by _ref
    seen_refs = set()
    unique_fixed = []
    for obj in fixed_addrs:
        if obj["_ref"] not in seen_refs:
            seen_refs.add(obj["_ref"])
            unique_fixed.append(obj)

    if unique_fixed:
        print(f"   Found {len(unique_fixed)} fixed addresses")
        for obj in unique_fixed:
            if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                deleted_count += 1
            else:
                failed_count += 1

    # 3. Delete DHCP ranges
    print("\n3. Finding and deleting DHCP ranges...")
    ranges = get_objects_by_comment(base_url, auth, "range", "comment", "claude_")
    if ranges:
        print(f"   Found {len(ranges)} DHCP ranges")
        for obj in ranges:
            if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                deleted_count += 1
            else:
                failed_count += 1

    # 4. Delete DNS zones
    print("\n4. Finding and deleting DNS zones...")
    zones = get_objects_by_fqdn(base_url, auth, "zone_auth", "claude")
    if zones:
        print(f"   Found {len(zones)} zones")
        for obj in zones:
            if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                deleted_count += 1
            else:
                failed_count += 1

    # 5. Delete networks
    print("\n5. Finding and deleting networks...")
    networks = get_objects_by_comment(base_url, auth, "network", "comment", "claude_")
    if networks:
        print(f"   Found {len(networks)} networks")
        for obj in networks:
            if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                deleted_count += 1
            else:
                failed_count += 1

    # 6. Delete network containers (last, as they contain networks)
    print("\n6. Finding and deleting network containers...")
    containers = get_objects_by_comment(base_url, auth, "networkcontainer", "comment", "claude_")
    if containers:
        print(f"   Found {len(containers)} containers")
        for obj in containers:
            if delete_object(base_url, auth, obj["_ref"], args.dry_run):
                deleted_count += 1
            else:
                failed_count += 1

    # Summary
    print()
    print("=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    if args.dry_run:
        print(f"Would delete: {deleted_count} objects")
    else:
        print(f"Deleted: {deleted_count} objects")
        print(f"Failed:  {failed_count} objects")
    print("=" * 60)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
