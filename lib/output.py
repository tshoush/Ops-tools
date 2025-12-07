"""
Output formatters - Always generates both JSON and CSV.
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from .config import load_config


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten nested dict for CSV output.

    Args:
        d: Dictionary to flatten
        parent_key: Prefix for nested keys
        sep: Separator between key levels

    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                # List of dicts - stringify
                items.append((new_key, json.dumps(v)))
            else:
                # Simple list - join with semicolons
                items.append((new_key, '; '.join(str(i) for i in v)))
        else:
            items.append((new_key, v))

    return dict(items)


class OutputWriter:
    """Handles writing output to JSON and CSV files."""

    def __init__(self, command_name: str, query: str = "", quiet: bool = False):
        """
        Initialize output writer.

        Args:
            command_name: Name of the command (used in filename)
            query: Query string (used in filename)
            quiet: Suppress console output
        """
        config = load_config()
        output_config = config.get("output", {})

        self.output_dir = Path(output_config.get("default_dir", "./output"))
        self.timestamp_files = output_config.get("timestamp_files", True)
        self.command_name = command_name
        self.query = self._sanitize_filename(query)
        self.quiet = quiet

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use in filename."""
        # Replace problematic characters
        replacements = {
            '/': '_',
            '\\': '_',
            ':': '-',
            ' ': '_',
            '*': '',
            '?': '',
            '"': '',
            '<': '',
            '>': '',
            '|': '_'
        }
        result = name
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result[:50]  # Limit length

    def _get_filename(self, extension: str) -> Path:
        """Generate output filename."""
        if self.timestamp_files:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{self.command_name}_{self.query}_{ts}.{extension}"
        else:
            name = f"{self.command_name}_{self.query}.{extension}"
        return self.output_dir / name

    def write(
        self,
        data: Union[Dict, List],
        summary: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Write data to both JSON and CSV files.

        Args:
            data: The data to write (dict or list of dicts)
            summary: Optional summary for console display

        Returns:
            Dict with paths to generated files {'json': path, 'csv': path}
        """
        # Normalize data to list for CSV
        if isinstance(data, dict):
            records = [data]
            json_data = data
        else:
            records = data if data else []
            json_data = data

        timestamp = datetime.now().isoformat()

        # Write JSON
        json_path = self._get_filename("json")
        output_json = {
            "metadata": {
                "command": self.command_name,
                "query": self.query,
                "timestamp": timestamp,
                "count": len(records)
            },
            "data": json_data
        }

        with open(json_path, 'w') as f:
            json.dump(output_json, f, indent=2, default=str)

        # Write CSV
        csv_path = self._get_filename("csv")
        if records:
            flat_records = [flatten_dict(r) for r in records]

            # Collect all keys across all records
            all_keys = set()
            for r in flat_records:
                all_keys.update(r.keys())

            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(flat_records)
        else:
            # Empty CSV with metadata
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["no_results"])
                writer.writerow([f"query: {self.query}"])
                writer.writerow([f"timestamp: {timestamp}"])

        # Console output (unless quiet mode)
        if not self.quiet:
            from .ui.colors import success, bold, dim

            print(f"\n{'=' * 60}")
            print(f"  Command:  {bold(self.command_name)}")
            print(f"  Query:    {self.query}")
            print(f"  Results:  {len(records)} record(s)")
            print(f"{'=' * 60}")

            if summary:
                print(f"\n  {bold('Summary:')}")
                for key, value in summary.items():
                    print(f"    {key}: {value}")

            print(f"\n  {bold('Output Files:')}")
            print(f"    JSON: {success(str(json_path))}")
            print(f"    CSV:  {success(str(csv_path))}")

        return {
            "json": str(json_path.absolute()),
            "csv": str(csv_path.absolute())
        }


def write_output(
    command: str,
    query: str,
    data: Union[Dict, List],
    quiet: bool = False,
    summary: Optional[Dict] = None
) -> Dict[str, str]:
    """
    Convenience function to write output.

    Args:
        command: Command name
        query: Query string
        data: Data to write
        quiet: Suppress console output
        summary: Optional summary dict

    Returns:
        Dict with output file paths
    """
    writer = OutputWriter(command, query, quiet=quiet)
    return writer.write(data, summary=summary)
