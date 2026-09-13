"""Interfaces layer.

HTTP (FastAPI, future) and CLI entry points. May depend on ``application`` and
``domain``; must not reach into ``infrastructure`` implementation details.
"""