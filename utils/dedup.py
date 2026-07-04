"""
Deduplication module for Vietstock Crawler
Checks if URLs already exist in CSV to avoid duplicates
"""

import pandas as pd
from pathlib import Path
from typing import Set, Optional
from config import CSV_FILE, CSV_HEADERS


class DedupManager:
    """Manages deduplication of crawled data"""

    def __init__(self, csv_file: Path = CSV_FILE):
        self.csv_file = csv_file
        self._existing_urls: Optional[Set[str]] = None
        self._existing_ids: Optional[Set[str]] = None

    def load_existing_data(self) -> None:
        """Load existing URLs and IDs from CSV into memory"""
        self._existing_urls = set()
        self._existing_ids = set()

        if not self.csv_file.exists():
            return

        try:
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            if 'pdf_url' in df.columns:
                self._existing_urls = set(df['pdf_url'].dropna().astype(str).tolist())
            if 'id' in df.columns:
                self._existing_ids = set(df['id'].dropna().astype(str).tolist())
        except Exception as e:
            print(f"Warning: Could not load existing data: {e}")
            self._existing_urls = set()
            self._existing_ids = set()

    @property
    def existing_urls(self) -> Set[str]:
        """Get set of existing URLs, loading from CSV if not already loaded"""
        if self._existing_urls is None:
            self.load_existing_data()
        return self._existing_urls if self._existing_urls is not None else set()

    @property
    def existing_ids(self) -> Set[str]:
        """Get set of existing IDs, loading from CSV if not already loaded"""
        if self._existing_ids is None:
            self.load_existing_data()
        return self._existing_ids if self._existing_ids is not None else set()

    def is_duplicate(self, url: str, check_id: Optional[str] = None) -> bool:
        """
        Check if a URL or ID already exists in the CSV

        Args:
            url: The PDF URL to check
            check_id: Optional ID to check

        Returns:
            True if the URL or ID already exists, False otherwise
        """
        if url in self.existing_urls:
            return True
        if check_id and check_id in self.existing_ids:
            return True
        return False

    def add_to_seen(self, url: str, id_value: Optional[str] = None) -> None:
        """
        Add a URL and/or ID to the seen sets

        Args:
            url: The URL to add
            id_value: Optional ID to add
        """
        self._existing_urls.add(url)
        if id_value:
            self._existing_ids.add(id_value)

    def init_csv_file(self) -> None:
        """Initialize CSV file with headers if it doesn't exist"""
        if not self.csv_file.exists():
            self.csv_file.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=CSV_HEADERS).to_csv(self.csv_file, index=False, encoding='utf-8')


# Global dedup manager instance
_dedup_manager: Optional[DedupManager] = None


def get_dedup_manager() -> DedupManager:
    """Get or create the global dedup manager instance"""
    global _dedup_manager
    if _dedup_manager is None:
        _dedup_manager = DedupManager()
        _dedup_manager.load_existing_data()
    return _dedup_manager
