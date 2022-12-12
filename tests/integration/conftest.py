"""Contains pytest configuration for integration tests."""
from dotenv import dotenv_values
import pysolr
import pytest


_from_dotenv = dotenv_values('integration/.env')
SOLR_HOST = _from_dotenv.get('TEST_SOLR_HOST', '127.0.0.1')
SOLR_PORT = _from_dotenv.get('TEST_SOLR_PORT', '8983')
SOLR_CORE = _from_dotenv.get('TEST_SOLR_CORE', 'test_core')
SOLR_URL = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_CORE}'


@pytest.fixture(scope='function')
def solrconn():
    """Fixture: yields a connection to the Solr test core.

    This also issues a "delete" command after each test runs to ensure
    a clean slate for the next test.
    """
    conn = pysolr.Solr(SOLR_URL)
    yield conn
    conn.delete(q='*:*', commit=True)
