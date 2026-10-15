"""Models: frozen, typed dataclasses for SWPC products.

Every time is a ``datetime`` in UTC. Each model exposes ``data_time`` (the
most recent time declared by the content), ``source_url``, and ``issued``,
``observed``, ``valid_from`` or ``valid_to`` where the source provides them.
"""
