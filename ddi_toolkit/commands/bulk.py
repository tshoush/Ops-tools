"""
Bulk operations command - Create, Modify, Delete objects from CSV/JSON files.
"""

import csv
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from .base import BaseCommand
from ..wapi import WAPIError


# Supported object types and their WAPI mappings
SUPPORTED_OBJECT_TYPES = {
    "network": {
        "wapi_type": "network",
        "required_fields": ["network"],
        "optional_fields": ["comment", "network_view", "options", "members", "extattrs"],
        "identifier_field": "network",
    },
    "networkcontainer": {
        "wapi_type": "networkcontainer",
        "required_fields": ["network"],
        "optional_fields": ["comment", "network_view", "extattrs"],
        "identifier_field": "network",
    },
    "host": {
        "wapi_type": "record:host",
        "required_fields": ["name", "ipv4addrs"],
        "optional_fields": ["comment", "view", "ttl", "extattrs"],
        "identifier_field": "name",
    },
    "a": {
        "wapi_type": "record:a",
        "required_fields": ["name", "ipv4addr"],
        "optional_fields": ["comment", "view", "ttl", "extattrs"],
        "identifier_field": "name",
    },
    "cname": {
        "wapi_type": "record:cname",
        "required_fields": ["name", "canonical"],
        "optional_fields": ["comment", "view", "ttl", "extattrs"],
        "identifier_field": "name",
    },
    "ptr": {
        "wapi_type": "record:ptr",
        "required_fields": ["ptrdname", "ipv4addr"],
        "optional_fields": ["comment", "view", "ttl", "extattrs"],
        "identifier_field": "ptrdname",
    },
    "mx": {
        "wapi_type": "record:mx",
        "required_fields": ["name", "mail_exchanger", "preference"],
        "optional_fields": ["comment", "view", "ttl"],
        "identifier_field": "name",
    },
    "txt": {
        "wapi_type": "record:txt",
        "required_fields": ["name", "text"],
        "optional_fields": ["comment", "view", "ttl"],
        "identifier_field": "name",
    },
    "fixedaddress": {
        "wapi_type": "fixedaddress",
        "required_fields": ["ipv4addr", "mac"],
        "optional_fields": ["name", "comment", "network_view", "options", "extattrs"],
        "identifier_field": "ipv4addr",
    },
    "zone": {
        "wapi_type": "zone_auth",
        "required_fields": ["fqdn"],
        "optional_fields": ["comment", "view", "zone_format", "extattrs"],
        "identifier_field": "fqdn",
    },
    "range": {
        "wapi_type": "range",
        "required_fields": ["start_addr", "end_addr", "network"],
        "optional_fields": ["comment", "network_view", "options", "name", "extattrs"],
        "identifier_field": "start_addr",
    },
}


class BulkCommand(BaseCommand):
    """Bulk create/modify/delete InfoBlox objects from CSV or JSON files."""

    name = "bulk"
    description = "Bulk operations: create, modify, or delete objects from file"
    aliases = ["import", "batch"]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute bulk operation.

        Args:
            query: Operation type ('create', 'modify', 'delete')
            object_type: Type of object (network, host, a, cname, etc.)
            file: Path to CSV or JSON file
            dry_run: Preview changes without executing
            continue_on_error: Continue processing after errors

        Returns:
            Results dict with success/failure counts and details
        """
        operation = query.lower()
        object_type = kwargs.get("object_type", "").lower()
        file_path = kwargs.get("file")
        dry_run = kwargs.get("dry_run", False)
        continue_on_error = kwargs.get("continue_on_error", True)

        # Validate operation
        if operation not in ["create", "modify", "delete"]:
            return {
                "error": f"Invalid operation: {operation}",
                "hint": "Valid operations: create, modify, delete"
            }

        # Validate object type
        if object_type not in SUPPORTED_OBJECT_TYPES:
            return {
                "error": f"Unsupported object type: {object_type}",
                "supported_types": list(SUPPORTED_OBJECT_TYPES.keys())
            }

        # Validate file
        if not file_path:
            return {
                "error": "No file specified",
                "hint": "Use --file to specify input CSV or JSON file"
            }

        file_path = Path(file_path)
        if not file_path.exists():
            return {
                "error": f"File not found: {file_path}",
                "hint": "Check the file path"
            }

        # Load objects from file
        try:
            objects = self._load_file(file_path)
        except Exception as e:
            return {
                "error": f"Failed to load file: {e}",
                "file": str(file_path)
            }

        if not objects:
            return {
                "error": "No objects found in file",
                "file": str(file_path)
            }

        # Validate objects
        type_config = SUPPORTED_OBJECT_TYPES[object_type]
        validation_errors = self._validate_objects(objects, type_config, operation)

        if validation_errors and not continue_on_error:
            return {
                "error": "Validation failed",
                "validation_errors": validation_errors,
                "total_objects": len(objects)
            }

        # Execute operation
        start_time = time.time()

        if operation == "create":
            results = self._bulk_create(objects, type_config, dry_run, continue_on_error)
        elif operation == "modify":
            results = self._bulk_modify(objects, type_config, dry_run, continue_on_error)
        elif operation == "delete":
            results = self._bulk_delete(objects, type_config, dry_run, continue_on_error)

        elapsed_time = time.time() - start_time

        # Build response
        response = {
            "operation": operation,
            "object_type": object_type,
            "wapi_type": type_config["wapi_type"],
            "file": str(file_path),
            "dry_run": dry_run,
            "total": len(objects),
            "successful": len(results["successful"]),
            "failed": len(results["errors"]),
            "success_rate": f"{len(results['successful']) / len(objects) * 100:.1f}%" if objects else "0%",
            "elapsed_seconds": round(elapsed_time, 2),
            "successful_operations": results["successful"],
            "errors": results["errors"],
            "validation_warnings": validation_errors if validation_errors else [],
            "_summary": {
                "Operation": operation.upper(),
                "Object Type": object_type,
                "Total": len(objects),
                "Successful": len(results["successful"]),
                "Failed": len(results["errors"]),
                "Success Rate": f"{len(results['successful']) / len(objects) * 100:.1f}%" if objects else "0%",
                "Duration": f"{elapsed_time:.2f}s",
                "Dry Run": "Yes" if dry_run else "No"
            }
        }

        return response

    def _load_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load objects from CSV or JSON file."""
        suffix = file_path.suffix.lower()

        if suffix == ".json":
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Handle both array and single object
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Check if it's wrapped in a data key
                    if "data" in data and isinstance(data["data"], list):
                        return data["data"]
                    return [data]
                return []

        elif suffix == ".csv":
            objects = []
            with open(file_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up the row - remove empty values
                    obj = {}
                    for key, value in row.items():
                        if value is not None and value.strip() != "":
                            # Try to parse JSON for complex fields
                            if value.startswith('[') or value.startswith('{'):
                                try:
                                    obj[key] = json.loads(value)
                                except json.JSONDecodeError:
                                    obj[key] = value
                            else:
                                obj[key] = value
                    if obj:
                        objects.append(obj)
            return objects

        else:
            raise ValueError(f"Unsupported file format: {suffix}. Use .json or .csv")

    def _validate_objects(
        self,
        objects: List[Dict],
        type_config: Dict,
        operation: str
    ) -> List[Dict]:
        """Validate objects before processing."""
        errors = []
        required_fields = type_config["required_fields"]
        identifier_field = type_config["identifier_field"]

        for idx, obj in enumerate(objects):
            obj_id = obj.get(identifier_field, f"row_{idx + 1}")

            # For delete, we need _ref
            if operation == "delete":
                if "_ref" not in obj:
                    # Check if we can look up by identifier
                    if identifier_field not in obj:
                        errors.append({
                            "index": idx,
                            "identifier": obj_id,
                            "error": f"Missing _ref or {identifier_field} for delete"
                        })
                continue

            # For create/modify, check required fields
            if operation == "create":
                for field in required_fields:
                    if field not in obj:
                        errors.append({
                            "index": idx,
                            "identifier": obj_id,
                            "error": f"Missing required field: {field}"
                        })

            # For modify, we need _ref or identifier
            if operation == "modify":
                if "_ref" not in obj and identifier_field not in obj:
                    errors.append({
                        "index": idx,
                        "identifier": obj_id,
                        "error": f"Missing _ref or {identifier_field} for modify"
                    })

        return errors

    def _bulk_create(
        self,
        objects: List[Dict],
        type_config: Dict,
        dry_run: bool,
        continue_on_error: bool
    ) -> Dict[str, List]:
        """Create multiple objects."""
        successful = []
        errors = []
        wapi_type = type_config["wapi_type"]
        identifier_field = type_config["identifier_field"]

        for idx, obj in enumerate(objects):
            obj_id = obj.get(identifier_field, f"row_{idx + 1}")

            if dry_run:
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "would_create",
                    "data": obj
                })
                continue

            try:
                # Remove any _ref from create data
                create_data = {k: v for k, v in obj.items() if k != "_ref"}
                ref = self.client.create(wapi_type, create_data)
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "created",
                    "_ref": ref
                })
            except WAPIError as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": e.message,
                    "data": obj
                })
                if not continue_on_error:
                    break
            except Exception as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": str(e),
                    "data": obj
                })
                if not continue_on_error:
                    break

        return {"successful": successful, "errors": errors}

    def _bulk_modify(
        self,
        objects: List[Dict],
        type_config: Dict,
        dry_run: bool,
        continue_on_error: bool
    ) -> Dict[str, List]:
        """Modify multiple objects."""
        successful = []
        errors = []
        wapi_type = type_config["wapi_type"]
        identifier_field = type_config["identifier_field"]

        for idx, obj in enumerate(objects):
            obj_id = obj.get(identifier_field, f"row_{idx + 1}")

            # Get _ref - either provided or look up
            ref = obj.get("_ref")
            if not ref:
                # Look up by identifier
                try:
                    lookup_params = {identifier_field: obj.get(identifier_field)}
                    existing = self.client.get(wapi_type, params=lookup_params)
                    if existing:
                        ref = existing[0].get("_ref")
                    else:
                        errors.append({
                            "index": idx,
                            "identifier": obj_id,
                            "error": f"Object not found: {obj.get(identifier_field)}"
                        })
                        if not continue_on_error:
                            break
                        continue
                except WAPIError as e:
                    errors.append({
                        "index": idx,
                        "identifier": obj_id,
                        "error": f"Lookup failed: {e.message}"
                    })
                    if not continue_on_error:
                        break
                    continue

            if dry_run:
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "would_modify",
                    "_ref": ref,
                    "changes": {k: v for k, v in obj.items() if k not in ["_ref", identifier_field]}
                })
                continue

            try:
                # Remove _ref and identifier from update data
                update_data = {k: v for k, v in obj.items() if k not in ["_ref", identifier_field]}
                result_ref = self.client.update(ref, update_data)
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "modified",
                    "_ref": result_ref
                })
            except WAPIError as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": e.message,
                    "_ref": ref
                })
                if not continue_on_error:
                    break
            except Exception as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": str(e),
                    "_ref": ref
                })
                if not continue_on_error:
                    break

        return {"successful": successful, "errors": errors}

    def _bulk_delete(
        self,
        objects: List[Dict],
        type_config: Dict,
        dry_run: bool,
        continue_on_error: bool
    ) -> Dict[str, List]:
        """Delete multiple objects."""
        successful = []
        errors = []
        wapi_type = type_config["wapi_type"]
        identifier_field = type_config["identifier_field"]

        for idx, obj in enumerate(objects):
            obj_id = obj.get(identifier_field, obj.get("_ref", f"row_{idx + 1}"))

            # Get _ref - either provided or look up
            ref = obj.get("_ref")
            if not ref:
                # Look up by identifier
                identifier_value = obj.get(identifier_field)
                if not identifier_value:
                    errors.append({
                        "index": idx,
                        "identifier": obj_id,
                        "error": f"Missing _ref or {identifier_field}"
                    })
                    if not continue_on_error:
                        break
                    continue

                try:
                    lookup_params = {identifier_field: identifier_value}
                    existing = self.client.get(wapi_type, params=lookup_params)
                    if existing:
                        ref = existing[0].get("_ref")
                    else:
                        errors.append({
                            "index": idx,
                            "identifier": obj_id,
                            "error": f"Object not found: {identifier_value}"
                        })
                        if not continue_on_error:
                            break
                        continue
                except WAPIError as e:
                    errors.append({
                        "index": idx,
                        "identifier": obj_id,
                        "error": f"Lookup failed: {e.message}"
                    })
                    if not continue_on_error:
                        break
                    continue

            if dry_run:
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "would_delete",
                    "_ref": ref
                })
                continue

            try:
                result_ref = self.client.delete(ref)
                successful.append({
                    "index": idx,
                    "identifier": obj_id,
                    "action": "deleted",
                    "_ref": result_ref
                })
            except WAPIError as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": e.message,
                    "_ref": ref
                })
                if not continue_on_error:
                    break
            except Exception as e:
                errors.append({
                    "index": idx,
                    "identifier": obj_id,
                    "error": str(e),
                    "_ref": ref
                })
                if not continue_on_error:
                    break

        return {"successful": successful, "errors": errors}


# Register command
command = BulkCommand
