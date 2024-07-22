class DiscobaseError(Exception):
    """Base discobase exception class."""


class NotConnectedError(DiscobaseError):
    """The database is not connected."""
