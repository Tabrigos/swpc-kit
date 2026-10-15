"""Parsers: pure functions from raw SWPC content to models.

Each parser takes ``str`` or ``bytes`` and returns a model from
:mod:`swpc_kit.models`. Parsers do no I/O and use only the standard library.
They accept every documented format of a product, old and new, and raise the
errors of :mod:`swpc_kit.errors` on bad input.
"""
