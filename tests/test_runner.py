"""Contains tests for `runner` module."""
import dataclasses
from pathlib import Path
from unittest.mock import call, Mock

import pytest

from solrbenchmark import docs, runner


# Fixtures / test data

@pytest.fixture
def new_mockconn():
    """Fixture: returns a func for generating a mock Solr connection."""
    def _new_mockconn(index_qts=None, commit_qts=None, terms_hits_qts=None):
        index_qt_iter = iter(index_qts or [])
        commit_qt_iter = iter(commit_qts or [])
        term_qt_iters = {}
        term_hits = {}
        for term, hits_qts in (terms_hits_qts or {}).items():
            term = term or ''
            hits, qtimes = hits_qts
            term_qt_iters[term] = iter(qtimes)
            term_hits[term] = hits

        def _search_response(q='', **kwargs):
            qt_iter = term_qt_iters.get(q) or iter([])
            return Mock(qtime=next(qt_iter, 0), hits=term_hits.get(q, 0))

        def _add_response(docs, **kwargs):
            return (f'{{\n'
                    f'  "responseHeader":{{\n'
                    f'    "status":0,\n'
                    f'    "QTime":{next(index_qt_iter, 0)}}}}}\n')

        def _commit_response(**kwargs):
            return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                    f'<response>\n'
                    f'\n'
                    f'<lst name="responseHeader">\n'
                    f'  <int name="status">0</int>\n'
                    f'  <int name="QTime">{next(commit_qt_iter, 0)}</int>\n'
                    f'</lst>\n'
                    f'</response>\n')

        mockconn = Mock()
        mockconn.search.side_effect = _search_response
        mockconn.add.side_effect = _add_response
        mockconn.commit.side_effect = _commit_response
        return mockconn
    return _new_mockconn


@pytest.fixture
def indexstats_sanity_check():
    """Fixture: returns a func for sanity checking test indexing stats.

    (I.e., from runner.BenchmarkRunner.)
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


# Note: built-in pytest fixture `tmpdir` is used for some tests. This
# creates a unique temporary directory for each test instance for
# testing file I/O. Files do NOT persist between tests.
#
# Additional fixtures defined in `conftest.py` are used:
#    simple_schema
#    configdata


# Tests

def test_configdata_derive(configdata):
    new_configdata = configdata.derive('new-configset', notes='New configset')
    assert new_configdata.config_id == 'new-configset'
    assert new_configdata.config_id != configdata.config_id
    assert new_configdata.notes == 'New configset'
    assert new_configdata.notes != configdata.notes
    for field_name, val in dataclasses.asdict(configdata).items():
        if field_name not in ('config_id', 'notes'):
            assert getattr(new_configdata, field_name) == val


def test_benchmarklog_saveto_and_loadfrom_jsonfile(configdata, tmpdir):
    docset_id = 'test-docset'
    istats = {'indexing': ['test']}
    sstats = {'search': ['test']}
    tlog = runner.BenchmarkLog(docset_id, configdata)
    tlog.indexing_stats = istats
    tlog.search_stats = sstats
    filepath = tmpdir / 'save_file.json'
    assert not filepath.exists()
    assert tlog.filepath is None
    filepath = tlog.save_to_json_file(filepath)
    assert filepath.exists()
    assert tlog.filepath == filepath
    del tlog

    new_tlog = runner.BenchmarkLog.load_from_json_file(filepath)
    assert new_tlog.configdata == configdata
    assert new_tlog.docset_id == docset_id
    assert new_tlog.indexing_stats == istats
    assert new_tlog.search_stats == sstats
    assert new_tlog.filepath == filepath


def test_benchmarklog_compilereport(configdata):
    tlog = runner.BenchmarkLog('test-docset', configdata)
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
            key for key in tlog.search_stats if key.startswith('no facets')
        ],
        'all facets GROUP': [
            key for key in tlog.search_stats if key.startswith('all facets')
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


def test_benchmarkrunner_no_logbasepath_save_error(configdata, new_mockconn):
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    with pytest.raises(ValueError) as excinfo:
        trunner.save_log()
    assert str(excinfo.value).startswith(
        'Attempted to save log data to `None`'
    )


def test_benchmarkrunner_save_logfile_behavior(configdata, new_mockconn,
                                               tmpdir):
    # This tests saving a logfile in various states using a realistic
    # multi-step workflow.
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    exp_filepath = Path(runner.compose_log_json_filepath(
        tmpdir, 'test', configdata.config_id
    ))

    # First, simulate some indexing stats.
    trunner.log.indexing_stats['a'] = 'test a'

    # Then save the log file to disk. The expected file should not
    # exist until we save it.
    assert not exp_filepath.exists()
    returned_filepath = trunner.save_log(tmpdir)
    assert trunner.logpath == returned_filepath == exp_filepath
    assert trunner.logpath.exists()
    # Capture the log contents at this stage for comparison later.
    log1 = runner.BenchmarkLog.load_from_json_file(exp_filepath)

    # Simulate getting search stats.
    trunner.log.search_stats['b'] = 'test b'

    # Now, save the log again. It should update the existing file.
    # Note that we don't need to include the basepath again when we
    # call trunner.save_log.
    returned_filepath2 = trunner.save_log()
    assert returned_filepath2 == exp_filepath

    # Capture log contents again and compare the earlier snapshot to
    # the new one.
    log2 = runner.BenchmarkLog.load_from_json_file(exp_filepath)
    assert log1.docset_id == log2.docset_id == 'test'
    assert log1.configdata == log2.configdata == configdata
    assert log1.indexing_stats == log2.indexing_stats == {'a': 'test a'}
    assert log1.search_stats == {}
    assert log2.search_stats == {'b': 'test b'}


def test_benchmarkrunner_load_logfile_behavior(configdata, new_mockconn,
                                               tmpdir):
    # Q: What if you want to re-run search tests for a specific config
    # but preserve the indexing tests that were already run?
    # A: Use `configure_from_saved_log` to load the logfile from disk.
    # Then run the search tests and save the file back to disk.
    lpath = Path(runner.compose_log_json_filepath(
        tmpdir, 'test', configdata.config_id
    ))

    # First we simulate an existing log file saved to disk.
    old_log = runner.BenchmarkLog('test', configdata)
    old_log.indexing_stats = {'a': 'original indexing stats'}
    old_log.search_stats = {'b': 'original search stats'}
    old_log.save_to_json_file(lpath)

    # Now create a BenchmarkRunner and load the configuration from that
    # saved file. (Confirm that it loaded correctly.)
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn).configure_from_saved_log(lpath)
    assert trunner.logpath == lpath
    assert trunner.log_basepath == lpath.parent
    assert trunner.log.docset_id == 'test'
    assert trunner.log.configdata == configdata
    assert trunner.log.indexing_stats == {'a': 'original indexing stats'}
    assert trunner.log.search_stats == {'b': 'original search stats'}

    # Finally, replace the search stats and save the file. Confirm that
    # the new search stats are saved but the old indexing stats are
    # intact.
    trunner.log.search_stats = {'c': 'new search stats'}
    trunner.save_log()
    new_log = runner.BenchmarkLog.load_from_json_file(lpath)
    assert new_log.docset_id == 'test'
    assert new_log.configdata == configdata
    assert new_log.indexing_stats == {'a': 'original indexing stats'}
    assert new_log.search_stats == {'c': 'new search stats'}


def test_benchmarkrunner_logpath_updates_itself(configdata, new_mockconn,
                                                tmpdir):
    # Q: Can you use the same test runner to run multiple tests and
    # just re-configure it each time? Does it save to different files
    # or do you have to manage that yourself?
    # A: You can use the same test runner for multiple configurations.
    # The `logpath` attribute updates automatically if you use a
    # different basepath or if you change the configuration.
    lpath = Path(runner.compose_log_json_filepath(
        tmpdir, 'test', configdata.config_id
    ))
    old_log = runner.BenchmarkLog('test', configdata)
    old_log.indexing_stats = {'a': 'original indexing stats'}
    old_log.search_stats = {'b': 'original search stats'}
    old_log.save_to_json_file(lpath)

    mockconn = new_mockconn()
    trunner1 = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    trunner1.log_basepath = tmpdir
    trunner2 = runner.BenchmarkRunner(mockconn).configure_from_saved_log(lpath)
    assert trunner1.logpath == trunner2.logpath == lpath

    trunner1.configure('t2', configdata)
    trunner2.configure('t2', configdata)
    assert trunner1.logpath == trunner2.logpath == Path(
        runner.compose_log_json_filepath(tmpdir, 't2', configdata.config_id)
    )
    configdata2 = configdata.derive('config-id2')
    trunner1.configure('t3', configdata2)
    trunner2.configure('t3', configdata2)
    assert trunner1.logpath == trunner2.logpath == Path(
        runner.compose_log_json_filepath(tmpdir, 't3', configdata2.config_id)
    )


def test_benchmarkrunner_indexdocs(configdata, simple_schema, new_mockconn,
                                   indexstats_sanity_check):
    batch_size = 10
    num_docs = 50
    myschema = simple_schema(num_docs, 0.5, 0.5, 999)
    docslist = [myschema() for _ in range(myschema.num_docs)]
    myschema.reset_fields()
    tdocset = docs.DocSet.from_schema('test-docset', myschema)
    mockconn = new_mockconn(index_qts=[9372, 2295, 11972, 5060, 8333],
                            commit_qts=[542, 368, 270, 985, 104])
    tr = runner.BenchmarkRunner(mockconn).configure(tdocset.id, configdata)
    stats = tr.index_docs(tdocset, batch_size=batch_size, verbose=True)
    indexstats_sanity_check(stats, batch_size, myschema.num_docs)
    assert tr.log.indexing_stats == stats
    mockconn.add.assert_has_calls(
        [call(docslist[i:i+batch_size], commit=False)
         for i in range(0, num_docs, batch_size)]
    )
    mockconn.commit.assert_has_calls([call()] * int(num_docs / batch_size))


def test_benchmarkrunner_indexdocs_not_configured(new_mockconn):
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn)
    docset = Mock(id='test')
    with pytest.raises(runner.RunnerConfigurationError) as excinfo:
        trunner.index_docs(docset)
    assert 'without adding configuration data' in str(excinfo.value)


def test_benchmarkrunner_indexdocs_wrong_docset(configdata, new_mockconn):
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    docset = Mock(id='WRONG')
    with pytest.raises(runner.RunnerConfigurationError) as excinfo:
        trunner.index_docs(docset)
    assert "(`WRONG`) does not match" in str(excinfo.value)
    assert str(excinfo.value).endswith('(`test`).')


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
def test_benchmarkrunner_search_controls(rep_n, ignore_n, qtimes, exp_qtime,
                                         configdata, new_mockconn):
    # With the rep_n argument, the runner should do/repeat the search N
    # times; with ignore_n, the runner should ignore the first N
    # searches. It should report the average qtime in ms from the ones
    # it does not ignore.
    mockconn = new_mockconn(terms_hits_qts={'test': (10, qtimes)})
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    info = trunner.search('test', {}, rep_n, ignore_n)
    assert info['qtime_ms'] == exp_qtime
    assert mockconn.search.call_count == rep_n


@pytest.mark.parametrize('q, kwargs, exp_hits, exp_qtime', [
    ('_aaa_', {}, 1, 123),
    ('_bbb_', {}, 2, 234),
    ('_ccc_', {}, 3, 345),
    ('_ddd_', {}, 4, 456),
    ('_eee_', {}, 5, 567),
    ('_aaa_', {'fq': 'colors:brown'}, 1, 678),
    ('_aaa_', {'fq': 'colors:green'}, 0, 789),
    ('_eee_', {'fq': 'colors:brown'}, 3, 891),
    ('_eee_', {'fq': 'colors:green AND colors:brown'}, 1, 912),
])
def test_benchmarkrunner_search_result(q, kwargs, exp_hits, exp_qtime,
                                       configdata, new_mockconn):
    mockconn = new_mockconn(terms_hits_qts={q: (exp_hits, [exp_qtime])})
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    info = trunner.search(q, kwargs, rep_n=1, ignore_n=0)
    assert info['hits'] == info['result'].hits == exp_hits
    assert info['qtime_ms'] == info['result'].qtime == exp_qtime
    mockconn.search.assert_called_once_with(q=q, **kwargs)


def test_benchmarkrunner_search_blankq(configdata, new_mockconn):
    # When `blank_q` is provided and `q` is blank, the `blank_q` value
    # should be used for `q` in the Solr search.
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    trunner.search('', {}, rep_n=1, ignore_n=0, blank_q='*:*')
    mockconn.search.assert_called_once_with(q='*:*', **{})


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
def test_benchmarkrunner_runsearches(terminfo, qkwargs, rep_n, ignore_n,
                                     exp_stats, new_mockconn, configdata):
    # The `run_searches` method should call `search` for each term in
    # `terms`, using the given query_kwargs, rep_n, and ignore_n args.
    # It should result in the expected stats.
    mockconn = new_mockconn(terms_hits_qts=terminfo)
    trunner = runner.BenchmarkRunner(mockconn).configure('test', configdata)
    stats = trunner.run_searches(terminfo.keys(), 'TEST', qkwargs, rep_n,
                                 ignore_n, blank_q='*:*', verbose=False)
    assert stats == exp_stats
    assert trunner.log.search_stats['TEST'] == stats
    mockconn.search.assert_has_calls(
        [call(q=q, **qkwargs) for q in terminfo for _ in range(rep_n)]
    )


def test_benchmarkrunner_runsearches_not_configured(new_mockconn):
    mockconn = new_mockconn()
    trunner = runner.BenchmarkRunner(mockconn)
    with pytest.raises(runner.RunnerConfigurationError) as excinfo:
        trunner.run_searches(['one', 'two'], 'TEST')
    assert 'without adding configuration data' in str(excinfo.value)
