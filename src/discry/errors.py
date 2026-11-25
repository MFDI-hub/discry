"""Errors raised while scraping or reading a published snapshot."""

from __future__ import annotations


class DiscryError(RuntimeError):
    """
    Base error for scrape failures and snapshot failures.

    Attributes:
        args (tuple[object, ...]): Message arguments supplied to the error.
    """

    __slots__ = ()
