from typing import Dict, Tuple

from pydantic import BaseModel


class Metadata(BaseModel):
    name: str
    """The table name."""
    keys: Tuple[str, ...]
    """A tuple containing the name of all keys/fields of the table."""
    table_channel: int
    """Channel ID that holds the main table content."""
    index_channels: Dict[str, int]
    """A dictionary containing index channel names with index channel IDs."""
    current_records: int
    """Number of (used) records in the table."""
    max_records: int
    """Capacity of the table (i.e. the "maximum records" that is can hold)."""
    message_id: int
    """ID of the metadata message."""
    hash_seed: int
    """Seed for the hash() function."""
