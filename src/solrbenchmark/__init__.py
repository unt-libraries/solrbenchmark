"""Tools for running Solr benchmarking tests."""
try:
    from importlib import metadata
except (ImportError, ModuleNotFoundError):
    import importlib_metadata as metadata
from . import docs
from . import runner
from . import schema
from . import terms


__version__ = metadata.version('solrbenchmark')
__all__ = [
    'docs', 'runner', 'schema', 'terms'
]
