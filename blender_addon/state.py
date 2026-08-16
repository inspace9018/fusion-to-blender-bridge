# Global singleton state — separated from __init__.py to prevent circular imports.
_handler = None
_client = None


def get_handler():
    return _handler


def get_client():
    return _client
