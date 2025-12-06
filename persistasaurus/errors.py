"""Custom exceptions for persistasaurus."""


class PersistasaurusError(Exception):
    """Base exception for persistasaurus-python."""


class NotFoundError(PersistasaurusError):
    """Raised when an execution or step is not found."""
