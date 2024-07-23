class DiscobaseError(Exception):
    """Base discobase exception class."""


class NotConnectedError(DiscobaseError):
    """The database is not connected."""


class DatabaseCorruptionError(DiscobaseError):
    """The database was corrupted somehow."""
