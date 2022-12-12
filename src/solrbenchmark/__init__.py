"""Tools for running Solr benchmarking tests."""
import sys

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

from . import docs
from . import runner
from . import schema
from . import terms


__version__ = metadata.version('solrbenchmark')
__all__ = [
    'docs', 'runner', 'schema', 'terms'
]
