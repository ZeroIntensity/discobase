class DiscobaseError(Exception):
    """
    Base discobase exception class.
    """


class NotConnectedError(DiscobaseError):
    """
    The database is not connected.
    """


class DatabaseCorruptionError(DiscobaseError):
    """
    The database was corrupted somehow.
    """


class DatabaseStorageError(DiscobaseError):
    """
    Failed store something in the database.
    """


class DatabaseTableError(DiscobaseError):
    """
    Something is wrong with a `Table` type.
    """


class DatabaseLookupError(DiscobaseError):
    """
    Something went wrong with an entry lookup.
    """
