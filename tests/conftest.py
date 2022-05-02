"""Contains pytest configuration."""
from dotenv import dotenv_values
import pysolr
import pytest


_from_dotenv = dotenv_values('.env')
SOLR_HOST = _from_dotenv.get('TEST_SOLR_HOST', '127.0.0.1')
SOLR_PORT = _from_dotenv.get('TEST_SOLR_PORT', '8983')
SOLR_URL = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/test_core'


@pytest.fixture(scope='function')
def solrconn():
    """Pytest fixture that yields a connection to the Solr test core.

    This also issues a "delete" command after each test runs to ensure
    a clean slate for the next test.
    """
    conn = pysolr.Solr(SOLR_URL)
    yield conn
    conn.delete(q='*:*', commit=True)
