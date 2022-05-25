"""Contains tests for `runner` module."""
from unittest.mock import call, Mock

import pytest

from solrbenchmark import docs, runner


# Fixtures / test data

@pytest.fixture
def new_mockconn():
    """Fixture: returns a func for generating a mock Solr connection."""
    def _new_mockconn(terms_hits_qts):
        term_qt_gens = {}
        term_hits = {}
        for term, hits_qts in terms_hits_qts.items():
            term = term or '*:*'
            hits, qtimes = hits_qts
            term_qt_gens[term] = (qt for qt in qtimes)
            term_hits[term] = hits

        def _side_effect(q='*:*', **kwargs):
            return Mock(qtime=next(term_qt_gens[q]), hits=term_hits[q])

        mockconn = Mock()
        mockconn.search.side_effect = _side_effect
        return mockconn
    return _new_mockconn


@pytest.fixture
def indexstats_sanity_check():
    """Fixture: returns a func for sanity checking test indexing stats.

    (I.e., from runner.BenchmarkTestRunner.)
    """
    def _indexstats_sanity_check(stats, batch_size, num_docs):
        uneven_batches = num_docs % batch_size
        num_batches = num_docs / batch_size + (1 if uneven_batches else 0)
        i_total = sum(stats['indexing_timings_secs'])
        i_avg = i_total / num_batches
        c_total = sum(stats['commit_timings_secs'])
        c_avg = c_total / num_batches
        assert stats['batch_size'] == batch_size
        assert stats['total_docs'] == num_docs
        assert len(stats['indexing_timings_secs']) == num_batches
        assert round(stats['indexing_total_secs'], 4) == round(i_total, 4)
        assert round(stats['indexing_average_secs'], 4) == round(i_avg, 4)
        assert len(stats['commit_timings_secs']) == num_batches
        assert round(stats['commit_total_secs'], 4) == round(c_total, 4)
        assert round(stats['commit_average_secs'], 4) == round(c_avg, 4)
        total = round(i_total + c_total, 4)
        assert round(stats['total_secs'], 4) == total
        assert round(stats['average_secs'], 4) == round(total / num_batches, 4)
    return _indexstats_sanity_check


@pytest.fixture
def assert_index_matches_docslist():
    """Fixture: returns a func for checking contents of a Solr index."""
    def _assert_index_matches_docslist(docslist, conn):
        results = list(conn.search('*:*', rows=len(docslist), sort='id asc'))

        # Solr does not return None for blank fields, so we have to
        # remove them from the expected docslist.
        exp_results = [
            {k: v for k, v in doc.items() if v is not None}
            for doc in docslist
        ]
        assert results == sorted(exp_results, key=lambda d: d['id'])
    return _assert_index_matches_docslist


@pytest.fixture
def test_doc_data():
    """Fixture: returns some data to use with simple_schema for tests."""
    return [
        {'id': '1', 'title': 'Test Doc 1', 'colors': ['grey', 'brown', 'blue'],
         'pattern': 'striped', 'title_search': '_aaa_ Test Doc 1',
         'colors_search': ['grey _ddd_', 'brown', '_bbb_'],
         'pattern_search': 'striped'},
        {'id': '2', 'title': 'Test Doc 2', 'colors': ['white', 'purple'],
         'pattern': 'checkered', 'title_search': '_ccc_ _bbb_',
         'colors_search': ['_ddd_', 'purple', 'red'],
         'pattern_search': 'checkered'},
        {'id': '3', 'title': 'Test Doc 3',
         'colors': ['black', 'yellow', 'orange'], 'pattern': 'plaid',
         'title_search': '_eee_',
         'colors_search': ['black', 'yellow', 'orange'],
         'pattern_search': 'plaid'},
        {'id': '4', 'title': 'Test Doc 4', 'colors': ['green', 'brown'],
         'pattern': 'solid', 'title_search': 'Test Doc 4',
         'colors_search': ['green _ccc_', 'brown', 'brown _eee_'],
         'pattern_search': 'solid'},
        {'id': '5', 'title': 'Test Doc 5', 'pattern': 'paisley',
         'title_search': 'Test Doc 5', 'pattern_search': 'paisley _eee_'},
        {'id': '6', 'title': 'Test Doc 6', 'colors': ['brown'],
         'pattern': 'striped', 'title_search': 'Test Doc 6',
         'colors_search': ['brown', 'br _fff_ own _eee_'],
         'pattern_search': 'striped'},
        {'id': '7', 'title': 'Test Doc 7', 'pattern': 'striped',
         'title_search': 'Test Doc 7', 'pattern_search': 'striped'},
        {'id': '8', 'title': 'Test Doc 8', 'colors': ['grey'],
         'pattern': 'striped', 'title_search': '_ggg_ _ddd_',
         'colors_search': ['grey'], 'pattern_search': 'striped'},
        {'id': '9', 'title': 'Test Doc 9', 'colors': ['brown'],
         'pattern': 'striped', 'title_search': '_hhh_ _ddd_',
         'colors_search': ['_eee_'], 'pattern_search': 'striped'},
        {'id': '10', 'title': 'Test Doc 10', 'colors': ['grey', 'blue'],
         'pattern': 'checkered', 'title_search': 'Test Doc 10',
         'colors_search': ['grey', '_ccc_ blue'],
         'pattern_search': 'checkered'}]


# Note: built-in pytest fixture `tmpdir` is used for some tests. This
# creates a unique temporary directory for each test instance for
# testing file I/O. Files do NOT persist between tests.
#
# Additional fixtures defined in `conftest.py` are used:
#    simple_schema
#    solrconn
#    metadata


# Tests

def test_benchmarktestlog_saveto_and_loadfrom_jsonfile(metadata, tmpdir):
    test_id = 'testlog_saveto_and_loadfrom_json_test'
    istats = {'indexing': ['test']}
    sstats = {'search': ['test']}
    tlog = runner.BenchmarkTestLog(test_id, metadata)
    tlog.indexing_stats = istats
    tlog.search_stats = sstats
    filepath = tmpdir / 'testlog.json'
    assert not filepath.exists()
    tlog.save_to_json_file(filepath)
    assert filepath.exists()
    del(tlog)

    new_tlog = runner.BenchmarkTestLog.load_from_json_file(filepath)
    assert new_tlog.metadata == metadata
    assert new_tlog.test_id == test_id
    assert new_tlog.indexing_stats == istats
    assert new_tlog.search_stats == sstats


def test_benchmarktestlog_compilereport(metadata):
    tlog = runner.BenchmarkTestLog('testlog_compilereport_test', metadata)
    tlog.indexing_stats = {
        'batch_size': 1000,
        'total_docs': 5000,
        'indexing_timings_secs': [10.9, 13.2, 8.43, 10.2, 11.63],
        'indexing_total_secs': 54.36,
        'indexing_average_secs': 10.872,
        'commit_timings_secs': [1.5, 3.2, 0.7, 1.1, 2.93],
        'commit_total_secs': 9.43,
        'commit_average_secs': 1.886,
        'total_secs': 63.79,
        'average_secs': 12.758
    }
    tlog.search_stats = {
        'no facets + no fq': {
            'term_results': [
                {'term': '', 'hits': 5000, 'qtime_ms': 203},
                {'term': 'one', 'hits': 10, 'qtime_ms': 101},
                {'term': 'two', 'hits': 150, 'qtime_ms': 567},
            ],
            'total_qtime_ms': 871,
            'avg_qtime_ms': 290.3333,
        },
        'all facets + no fq': {
            'term_results': [
                {'term': '', 'hits': 5000, 'qtime_ms': 2000},
                {'term': 'one', 'hits': 10, 'qtime_ms': 500},
                {'term': 'two', 'hits': 150, 'qtime_ms': 1000},
            ],
            'total_qtime_ms': 3500,
            'avg_qtime_ms': 1166.6667,
        },
        'no facets + first color facet value': {
            'term_results': [
                {'term': '', 'hits': 4300, 'qtime_ms': 450},
                {'term': 'one', 'hits': 8, 'qtime_ms': 50},
                {'term': 'two', 'hits': 103, 'qtime_ms': 200},
            ],
            'total_qtime_ms': 700,
            'avg_qtime_ms': 233.3333,
        },
        'no facets + middle color facet value': {
            'term_results': [
                {'term': '', 'hits': 1053, 'qtime_ms': 275},
                {'term': 'one', 'hits': 3, 'qtime_ms': 32},
                {'term': 'two', 'hits': 52, 'qtime_ms': 89},
            ],
            'total_qtime_ms': 396,
            'avg_qtime_ms': 132,
        },
        'no facets + last color facet value': {
            'term_results': [
                {'term': '', 'hits': 48, 'qtime_ms': 200},
                {'term': 'one', 'hits': 1, 'qtime_ms': 5},
                {'term': 'two', 'hits': 3, 'qtime_ms': 20},
            ],
            'total_qtime_ms': 225,
            'avg_qtime_ms': 75,
        },
        'all facets + first color facet value': {
            'term_results': [
                {'term': '', 'hits': 4300, 'qtime_ms': 850},
                {'term': 'one', 'hits': 8, 'qtime_ms': 420},
                {'term': 'two', 'hits': 103, 'qtime_ms': 515},
            ],
            'total_qtime_ms': 1785,
            'avg_qtime_ms': 595,
        },
        'all facets + middle color facet value': {
            'term_results': [
                {'term': '', 'hits': 1053, 'qtime_ms': 375},
                {'term': 'one', 'hits': 3, 'qtime_ms': 102},
                {'term': 'two', 'hits': 52, 'qtime_ms': 165},
            ],
            'total_qtime_ms': 642,
            'avg_qtime_ms': 214,
        },
        'all facets + last color facet value': {
            'term_results': [
                {'term': '', 'hits': 48, 'qtime_ms': 303},
                {'term': 'one', 'hits': 1, 'qtime_ms': 87},
                {'term': 'two', 'hits': 3, 'qtime_ms': 71},
            ],
            'total_qtime_ms': 461,
            'avg_qtime_ms': 153.6667,
        }
    }
    aggregate_search_groups = {
        'no facets GROUP': [
            l for l in tlog.search_stats if l.startswith('no facets')
        ],
        'all facets GROUP': [
            l for l in tlog.search_stats if l.startswith('all facets')
        ],
    }
    expected_report = {
        'ADD': {
            'total': (54.36, 's'),
            'avg per 1000 docs': (10.872, 's')
        },
        'COMMIT': {
            'total': (9.43, 's'),
            'avg per 1000 docs': (1.886, 's')
        },
        'INDEXING': {
            'total': (63.79, 's'),
            'avg per 1000 docs': (12.758, 's')
        },
        'SEARCH': {
            'BLANK': {
                'no facets + no fq': (203, 'ms'),
                'all facets + no fq': (2000, 'ms'),
                'no facets + first color facet value': (450, 'ms'),
                'no facets + middle color facet value': (275, 'ms'),
                'no facets + last color facet value': (200, 'ms'),
                'all facets + first color facet value': (850, 'ms'),
                'all facets + middle color facet value': (375, 'ms'),
                'all facets + last color facet value': (303, 'ms'),
                'no facets GROUP': (282, 'ms'),
                'all facets GROUP': (882, 'ms')
            },
            'ALL TERMS': {
                'no facets + no fq': (290.3333, 'ms'),
                'all facets + no fq': (1166.6667, 'ms'),
                'no facets + first color facet value': (233.3333, 'ms'),
                'no facets + middle color facet value': (132, 'ms'),
                'no facets + last color facet value': (75, 'ms'),
                'all facets + first color facet value': (595, 'ms'),
                'all facets + middle color facet value': (214, 'ms'),
                'all facets + last color facet value': (153.6667, 'ms'),
                'no facets GROUP': (182.6667, 'ms'),
                'all facets GROUP': (532.3333, 'ms')
            }
        }
    }
    assert tlog.compile_report(aggregate_search_groups) == expected_report


def test_benchmarktestrunner_indexdocs(metadata, simple_schema, solrconn,
                                       indexstats_sanity_check,
                                       assert_index_matches_docslist):
    assert_index_matches_docslist([], solrconn)
    batch_size = 10
    num_docs = 50
    myschema = simple_schema(num_docs, 0.5, 0.5, 999)
    docslist = [myschema() for _ in range(myschema.num_docs)]
    myschema.reset_fields()
    tdocset = docs.TestDocSet.from_schema(myschema)
    tlog = runner.BenchmarkTestLog('indexdocs_test', metadata)
    trunner = runner.BenchmarkTestRunner(tdocset, tlog, solrconn)
    stats = trunner.index_docs(batch_size=batch_size, verbose=False)
    indexstats_sanity_check(stats, batch_size, myschema.num_docs)
    assert trunner.test_log.indexing_stats == stats
    assert_index_matches_docslist(docslist, solrconn)


@pytest.mark.parametrize('rep_n, ignore_n, qtimes, exp_qtime', [
    (5, 0, [1000, 5, 3, 1, 20], 205.8),
    (4, 0, [1000, 5, 3, 1, 20], 252.25),
    (5, 1, [1000, 5, 3, 1, 20], 7.25),
    (4, 1, [1000, 5, 3, 1, 20], 3),
    (5, 2, [1000, 5, 3, 1, 20], 8),
    (4, 2, [1000, 5, 3, 1, 20], 2),
    (1, 0, [1000, 5, 3, 1, 20], 1000),
    (2, 0, [1000, 5, 3, 1, 20], 502.5),
    (5, 10, [1000, 5, 3, 1, 20], 0),
])
def test_benchmarktestrunner_search_controls(rep_n, ignore_n, qtimes,
                                             exp_qtime, metadata,
                                             new_mockconn):
    # With the rep_n argument, the runner should do/repeat the search N
    # times; with ignore_n, the runner should ignore the first N
    # searches. It should report the average qtime in ms from the ones
    # it does not ignore.
    mockconn = new_mockconn({'test': (10, qtimes)})
    tlog = runner.BenchmarkTestLog('searchdocs_controls_test', metadata)
    trunner = runner.BenchmarkTestRunner(None, tlog, mockconn)
    info = trunner.search('test', {}, rep_n, ignore_n)
    assert info['qtime_ms'] == exp_qtime
    assert mockconn.search.call_count == rep_n


@pytest.mark.parametrize('q, kwargs, exp_hits, exp_ids', [
    ('_aaa_', {}, 1, ['1']),
    ('_bbb_', {}, 2, ['1', '2']),
    ('_ccc_', {}, 3, ['2', '4', '10']),
    ('_ddd_', {}, 4, ['1', '2', '8', '9']),
    ('_eee_', {}, 5, ['3', '4', '5', '6', '9']),
    ('_aaa_', {'fq': 'colors:brown'}, 1, ['1']),
    ('_aaa_', {'fq': 'colors:green'}, 0, []),
    ('_eee_', {'fq': 'colors:brown'}, 3, ['4', '6', '9']),
    ('_eee_', {'fq': 'colors:green AND colors:brown'}, 1, ['4']),
])
def test_benchmarktestrunner_search_result(q, kwargs, exp_hits, exp_ids,
                                           metadata, test_doc_data, solrconn):
    tlog = runner.BenchmarkTestLog('searchdocs_test', metadata)
    trunner = runner.BenchmarkTestRunner(None, tlog, solrconn)
    solrconn.add(test_doc_data, commit=True)
    info = trunner.search(q, kwargs)
    result_ids = [r['id'] for r in info['result']]
    assert info['hits'] == exp_hits
    assert info['qtime_ms'] >= 0
    for doc_id in exp_ids:
        assert doc_id in result_ids


@pytest.mark.parametrize('terminfo, qkwargs, rep_n, ignore_n, exp_stats', [
    ({'one': (10, [500, 35, 20, 15, 23]),
      'two': (150, [1500, 120, 99, 140, 80])},
     {'fq': 'facet:value'}, 5, 1,
     {'total_qtime_ms': 133.0,
      'avg_qtime_ms': 66.5,
      'term_results': [{'term': 'one', 'hits': 10, 'qtime_ms': 23.25},
                       {'term': 'two', 'hits': 150, 'qtime_ms': 109.75}]}),
    ({'': (15000, [2100, 200, 30, 2, 1]),
      'one': (10, [450, 20, 20, 15, 3]),
      'two': (150, [1445, 100, 145, 50, 90])},
     {'fq': 'facet:value'}, 5, 0,
     {'total_qtime_ms': 934.2,
      'avg_qtime_ms': 311.4,
      'term_results': [{'term': '', 'hits': 15000, 'qtime_ms': 466.6},
                       {'term': 'one', 'hits': 10, 'qtime_ms': 101.6},
                       {'term': 'two', 'hits': 150, 'qtime_ms': 366.0}]})

])
def test_benchmarktestrunner_runsearches(terminfo, qkwargs, rep_n, ignore_n,
                                         exp_stats, new_mockconn, metadata):
    # The `run_searches` method should call `search` for each term in
    # `terms`, using the given query_kwargs, rep_n, and ignore_n args.
    # It should result in the expected stats.
    mockconn = new_mockconn(terminfo)
    tlog = runner.BenchmarkTestLog('runsearches_test', metadata)
    trunner = runner.BenchmarkTestRunner(None, tlog, mockconn)
    stats = trunner.run_searches(terminfo.keys(), 'TEST', qkwargs, rep_n,
                                 ignore_n, verbose=False)
    assert stats == exp_stats
    assert trunner.test_log.search_stats['TEST'] == stats
    mockconn.search.assert_has_calls(
        [call(q=q or '*:*', **qkwargs) for q in terminfo for _ in range(rep_n)]
    )
