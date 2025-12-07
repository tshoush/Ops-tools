"""
Base command class - All commands inherit from this.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from ..wapi import get_client, WAPIClient, WAPIError
from ..output import OutputWriter


class BaseCommand(ABC):
    """Abstract base class for all DDI commands."""

    # Override in subclasses
    name: str = "base"
    description: str = "Base command"
    aliases: List[str] = []

    def __init__(self):
        """Initialize command with WAPI client."""
        self._client: Optional[WAPIClient] = None

    @property
    def client(self) -> WAPIClient:
        """Lazy-load WAPI client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    @abstractmethod
    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute the command.

        Args:
            query: The primary query argument (IP, network, zone name, etc.)
            **kwargs: Additional options

        Returns:
            Dict containing the query results
        """
        pass

    def run(self, query: str, quiet: bool = False, **kwargs) -> Dict[str, str]:
        """
        Run command and write output.

        Args:
            query: Query string
            quiet: Suppress console output
            **kwargs: Additional options

        Returns:
            Dict with paths to output files
        """
        data = self.execute(query, **kwargs)

        # Extract summary if provided
        summary = None
        if isinstance(data, dict) and "_summary" in data:
            summary = data.pop("_summary")

        writer = OutputWriter(self.name, query, quiet=quiet)
        return writer.write(data, summary=summary)

    @classmethod
    def help(cls) -> str:
        """Return help text for this command."""
        return f"{cls.name}: {cls.description}"

    @classmethod
    def get_return_fields(cls) -> List[str]:
        """Get list of return fields for this command. Override in subclasses."""
        return []
