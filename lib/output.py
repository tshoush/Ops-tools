"""
Output formatters - Always generates both JSON and CSV.

Optimized for large datasets:
- Streams data directly to files to minimize memory usage
- Uses generators for processing large result sets
- Writes incrementally rather than building full data structures in memory
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Iterator, Generator
from .config import load_config

# Threshold for switching to streaming mode (number of records)
LARGE_DATASET_THRESHOLD = 5000


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

        record_count = len(records)
        timestamp = datetime.now().isoformat()

        # Use streaming for large datasets
        if record_count > LARGE_DATASET_THRESHOLD:
            return self._write_large(records, timestamp, summary)

        # Standard write for smaller datasets
        json_path = self._get_filename("json")
        output_json = {
            "metadata": {
                "command": self.command_name,
                "query": self.query,
                "timestamp": timestamp,
                "count": record_count
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

        self._print_summary(json_path, csv_path, record_count, summary)

        return {
            "json": str(json_path.absolute()),
            "csv": str(csv_path.absolute())
        }

    def _write_large(
        self,
        records: List[Dict],
        timestamp: str,
        summary: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Write large datasets using streaming to minimize memory usage.

        Writes JSON line-by-line and CSV row-by-row to avoid
        building large data structures in memory.
        """
        record_count = len(records)
        json_path = self._get_filename("json")
        csv_path = self._get_filename("csv")

        # Stream JSON - write incrementally
        with open(json_path, 'w') as f:
            # Write opening
            f.write('{\n')
            f.write(f'  "metadata": {{\n')
            f.write(f'    "command": "{self.command_name}",\n')
            f.write(f'    "query": "{self.query}",\n')
            f.write(f'    "timestamp": "{timestamp}",\n')
            f.write(f'    "count": {record_count}\n')
            f.write(f'  }},\n')
            f.write(f'  "data": [\n')

            # Write records one at a time
            for i, record in enumerate(records):
                record_json = json.dumps(record, indent=4, default=str)
                # Indent each line of the record
                indented = '\n'.join('    ' + line for line in record_json.split('\n'))
                f.write(indented)
                if i < record_count - 1:
                    f.write(',\n')
                else:
                    f.write('\n')

            f.write('  ]\n')
            f.write('}\n')

        # Stream CSV - collect keys from first batch, then write
        if records:
            # Sample first 100 records to get all possible keys
            sample_size = min(100, record_count)
            all_keys = set()
            for r in records[:sample_size]:
                flat = flatten_dict(r)
                all_keys.update(flat.keys())

            # Also check a few from the end in case schema varies
            if record_count > sample_size:
                for r in records[-10:]:
                    flat = flatten_dict(r)
                    all_keys.update(flat.keys())

            fieldnames = sorted(all_keys)

            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()

                # Write in batches to reduce I/O overhead
                batch_size = 1000
                for i in range(0, record_count, batch_size):
                    batch = records[i:i + batch_size]
                    flat_batch = [flatten_dict(r) for r in batch]
                    writer.writerows(flat_batch)
        else:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["no_results"])

        self._print_summary(json_path, csv_path, record_count, summary)

        return {
            "json": str(json_path.absolute()),
            "csv": str(csv_path.absolute())
        }

    def write_streamed(
        self,
        record_generator: Generator[List[Dict], None, None],
        summary: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Write data from a generator/iterator directly to files.

        Use this for very large datasets where you don't want to
        load all records into memory at once.

        Args:
            record_generator: Generator yielding batches of records
            summary: Optional summary for console display

        Returns:
            Dict with paths to generated files
        """
        timestamp = datetime.now().isoformat()
        json_path = self._get_filename("json")
        csv_path = self._get_filename("csv")

        record_count = 0
        all_keys = set()
        first_batch = True

        # Open both files for streaming
        with open(json_path, 'w') as json_file, \
             open(csv_path, 'w', newline='') as csv_file:

            # Write JSON header
            json_file.write('{\n')
            json_file.write(f'  "metadata": {{\n')
            json_file.write(f'    "command": "{self.command_name}",\n')
            json_file.write(f'    "query": "{self.query}",\n')
            json_file.write(f'    "timestamp": "{timestamp}",\n')
            json_file.write(f'    "count": "STREAMING"\n')  # Updated at end
            json_file.write(f'  }},\n')
            json_file.write(f'  "data": [\n')

            csv_writer = None

            for batch in record_generator:
                if not batch:
                    continue

                # Initialize CSV writer with keys from first batch
                if first_batch:
                    for r in batch[:100]:
                        flat = flatten_dict(r)
                        all_keys.update(flat.keys())
                    csv_writer = csv.DictWriter(
                        csv_file,
                        fieldnames=sorted(all_keys),
                        extrasaction='ignore'
                    )
                    csv_writer.writeheader()
                    first_batch = False

                # Write JSON records
                for record in batch:
                    if record_count > 0:
                        json_file.write(',\n')
                    record_json = json.dumps(record, indent=4, default=str)
                    indented = '\n'.join('    ' + line for line in record_json.split('\n'))
                    json_file.write(indented)
                    record_count += 1

                # Write CSV records
                if csv_writer:
                    flat_batch = [flatten_dict(r) for r in batch]
                    csv_writer.writerows(flat_batch)

            # Close JSON array
            json_file.write('\n  ]\n')
            json_file.write('}\n')

        # Update count in JSON (rewrite metadata section)
        # For simplicity, we leave "STREAMING" - could seek back and update

        self._print_summary(json_path, csv_path, record_count, summary)

        return {
            "json": str(json_path.absolute()),
            "csv": str(csv_path.absolute()),
            "count": record_count
        }

    def _print_summary(
        self,
        json_path: Path,
        csv_path: Path,
        record_count: int,
        summary: Optional[Dict] = None
    ):
        """Print console summary unless in quiet mode."""
        if not self.quiet:
            from .ui.colors import success, bold, dim

            print(f"\n{'=' * 60}")
            print(f"  Command:  {bold(self.command_name)}")
            print(f"  Query:    {self.query}")
            print(f"  Results:  {record_count} record(s)")
            print(f"{'=' * 60}")

            if summary:
                print(f"\n  {bold('Summary:')}")
                for key, value in summary.items():
                    print(f"    {key}: {value}")

            print(f"\n  {bold('Output Files:')}")
            print(f"    JSON: {success(str(json_path))}")
            print(f"    CSV:  {success(str(csv_path))}")


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
