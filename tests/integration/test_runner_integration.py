"""Contains integration test(s) for `runner` module.

These tests require an active Solr instance to run. You can either
provide your own test core that uses the configuration in the
`tests/solrconf` directory, or you can use Docker / docker-compose.

By default we expect Solr to run on 127.0.0.1:8983 using a core called
"test_core." You can change any of these values by setting them as
environment variables in a `tests/integration/.env` file. (Use
`tests/integration/template.env` as a template.) If the defaults are
fine, then you do not need to create the .env file.

To use Docker you must (of course) have Docker and docker-compose
installed. Run Solr by running `./docker-compose.sh up -d` from within
the `tests/integration` directory.

Tests expect the test core to start out empty, and they will clear it
out when complete. DO NOT USE IT FOR ANYTHING OTHER THAN THESE TESTS.
"""
import pytest

from solrbenchmark import docs, runner


# Fixtures / test data

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


# Tests below use built-in pytest fixture `tmpdir`. Other fixtures used
# are defined in `conftest.py`:
#    simple_schema
#    solrconn
#    configdata
#    indexstats_sanity_check


# Tests

def test_benchmarkrunner_indexdocs(configdata, simple_schema, solrconn,
                                   indexstats_sanity_check,
                                   assert_index_matches_docslist):
    assert_index_matches_docslist([], solrconn)
    batch_size = 10
    num_docs = 50
    myschema = simple_schema(num_docs, 0.5, 0.5, 999)
    docslist = [myschema() for _ in range(myschema.num_docs)]
    myschema.reset_fields()
    tdocset = docs.DocSet.from_schema('test-docset', myschema)
    tr = runner.BenchmarkRunner(solrconn).configure(tdocset.id, configdata)
    stats = tr.index_docs(tdocset, batch_size=batch_size, verbose=True)
    indexstats_sanity_check(stats, batch_size, myschema.num_docs)
    assert tr.log.indexing_stats == stats
    assert_index_matches_docslist(docslist, solrconn)


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
def test_benchmarkrunner_search_result(q, kwargs, exp_hits, exp_ids,
                                       configdata, test_doc_data, solrconn):
    trunner = runner.BenchmarkRunner(solrconn).configure('test', configdata)
    solrconn.add(test_doc_data, commit=True)
    info = trunner.search(q, kwargs)
    result_ids = [r['id'] for r in info['result']]
    assert info['hits'] == exp_hits
    assert info['qtime_ms'] >= 0
    for doc_id in exp_ids:
        assert doc_id in result_ids


def test_runner_integration(tmpdir, configdata, simple_schema, solrconn):
    # This is the big integration test that tests/illustrates the steps
    # for running benchmark tests from start to finish. Many of the
    # specifics are hidden away in fixtures, so this is mostly a high-
    # level view.

    # FIRST: Define and configure your schema (schema.BenchmarkSchema).
    myschema = simple_schema(10000, 1.0, 0.5, None)

    # SECOND: Set up your search test definitions.
    # The search terms we want to test include "blank" plus the terms
    # from the schema search term emitter.
    search_terms = [''] + myschema.search_terms

    # Definitions for each of our search runs are below. In these, we
    # want to run through the full batch of search terms with each of
    # the given sets of constraints in place. (Requesting no facet
    # listings and full facet listings, plus an fq limit using each of
    # a high-, mid-, and low-cardinality value from each facet.) We
    # could also do tests that limit to e.g. high-hit search terms.
    colors = myschema.fields['colors'].terms
    pattern = myschema.fields['pattern'].terms
    all_facets_kwargs = {
        'facet': 'true', 'facet.field': ['colors', 'pattern'],
        'f.colors.facet.limit': 5, 'f.pattern.facet.limit': 5
    }
    search_run_defs = {
        'no facets + no fq': {},
        'all facets + no fq': dict(all_facets_kwargs),
        'no facets + 1st `colors` facet value': {
            'fq': f'colors:{colors[0]}'
        },
        'all facets + 1st `colors` facet value': dict(all_facets_kwargs, **{
            'fq': f'colors:{colors[0]}'
        }),
        'no facets + mid `colors` facet value': {
            'fq': f'colors:{colors[round((len(colors) - 1) / 2)]}'
        },
        'all facets + mid `colors` facet value': dict(all_facets_kwargs, **{
            'fq': f'colors:{colors[round((len(colors) - 1) / 2)]}'
        }),
        'no facets + last `colors` facet value': {
            'fq': f'colors:{colors[-1]}'
        },
        'all facets + last `colors` facet value': dict(all_facets_kwargs, **{
            'fq': f'colors:{colors[-1]}'
        }),
        'no facets + 1st `pattern` facet value': {
            'fq': f'pattern:{pattern[0]}'
        },
        'all facets + 1st `pattern` facet value': dict(all_facets_kwargs, **{
            'fq': f'pattern:{pattern[0]}'
        }),
        'no facets + mid `pattern` facet value': {
            'fq': f'pattern:{pattern[round((len(pattern) - 1) / 2)]}'
        },
        'all facets + mid `pattern` facet value': dict(all_facets_kwargs, **{
            'fq': f'pattern:{pattern[round((len(pattern) - 1) / 2)]}'
        }),
        'no facets + last `pattern` facet value': {
            'fq': f'pattern:{pattern[-1]}'
        },
        'all facets + last `pattern` facet value': dict(all_facets_kwargs, **{
            'fq': f'pattern:{pattern[-1]}'
        }),
    }
    # When we later compile the report, we can send definitions for
    # aggregate groups we want to tabulate from the raw data; this will
    # give us, e.g., averages for all searches without facet counts and
    # all searches with facet counts. You just compile groups of labels
    # from your base search defs and apply a label to each group.
    search_groups = {
        'no facets GROUP': [
            rdef for rdef in search_run_defs if rdef.startswith('no facets')
        ],
        'all facets GROUP': [
            rdef for rdef in search_run_defs if rdef.startswith('all facets')
        ],
    }

    # THIRD: Set up system configuration data for your tests. Here we
    # use a fixture, so it's a bit glossed over, but this is a data
    # structure where you record details about all the various Solr /
    # system parameters that are under test. E.g.:
    # configdata = runner.ConfigData(
    #     config_id='250M heap',
    #     solr_version='8.11',
    #     jvm_memory='-Xmx250M',
    #     ...
    # )

    # If you're running multiple tests to compare different setups,
    # you'll want multiple sets of configuration. Ideally you'll only
    # be changing one aspect of the configuration per test, so you can
    # easily just derive a new configdata instance from the old one and
    # override the setting you're testing.
    configdata2 = configdata.derive('500M heap', jvm_memory='-Xmx500')

    # FOURTH: Instantiate a docset (docs.DocSet). We also provide a
    # path to save our test docset to disk so we can run multiple
    # tests seamlessly.
    tdocset = docs.DocSet.from_schema('test-docset', myschema, savepath=tmpdir)

    # FIFTH: Run the tests. In this example we've set up two system
    # configurations, which translates to two separate test runs. In a
    # real-life scenario we would have to ensure our tests are actually
    # running against a Solr instance that's configured the way we
    # assert that it is in our ConfigData objects. This could involve
    # running multiple Solr instances and passing different `solrconn`
    # objects to each runner. Or it could involve pausing between each
    # test to reconfigure and reset the Solr environment. Or you could
    # automate it using e.g. Docker. For this test we don't actually
    # care about this, so we're just going to run the two tests in
    # sequence.
    ds_id = tdocset.id
    trunner = runner.BenchmarkRunner(solrconn).configure(ds_id, configdata)
    i_stats1 = trunner.index_docs(tdocset, batch_size=1000)
    s_stats1 = {
        label: trunner.run_searches(search_terms, label, qargs, 5, 0, '*:*',
                                    False)
        for label, qargs in search_run_defs.items()
    }
    logpath1 = trunner.save_log(tmpdir)
    solrconn.delete(q='*:*', commit=True)
    # Note: For the second configuration, we can either run `configure`
    # again on the existing BenchmarkRunner object or init a new one.
    trunner.configure(ds_id, configdata2)
    i_stats2 = trunner.index_docs(tdocset, batch_size=1000)
    s_stats2 = {
        label: trunner.run_searches(search_terms, label, qargs, 5, 0, '*:*',
                                    False)
        for label, qargs in search_run_defs.items()
    }
    logpath2 = trunner.save_log(tmpdir)

    # SIXTH: Compile a final report for each test.
    log1 = runner.BenchmarkLog.load_from_json_file(logpath1)
    log2 = runner.BenchmarkLog.load_from_json_file(logpath2)
    report1 = log1.compile_report(search_groups)
    report2 = log2.compile_report(search_groups)

    # This last section is for our assertions to make sure we're
    # getting sane values for things.
    assert i_stats1 == log1.indexing_stats
    assert s_stats1 == log1.search_stats
    assert i_stats2 == log2.indexing_stats
    assert s_stats2 == log2.search_stats
    assert i_stats1 != i_stats2
    assert s_stats1 != s_stats2
    assert list(report1.keys()) == ['ADD', 'COMMIT', 'INDEXING', 'SEARCH']
    assert list(report2.keys()) == ['ADD', 'COMMIT', 'INDEXING', 'SEARCH']
    search_labels = list(search_run_defs.keys()) + list(search_groups.keys())
    assert list(report1['SEARCH']['BLANK'].keys()) == search_labels
    assert list(report2['SEARCH']['BLANK'].keys()) == search_labels
    assert list(report1['SEARCH']['ALL TERMS'].keys()) == search_labels
    assert list(report2['SEARCH']['ALL TERMS'].keys()) == search_labels

    filepaths = tdocset.fileset.filepaths
    assert all(fp.exists() for fp in filepaths)
    assert logpath1.exists()
    assert logpath2.exists()

    # With batches of 1000 docs, timings for indexing should all be >0.
    for action in ('ADD', 'COMMIT', 'INDEXING'):
        total1, _ = report1[action]['total']
        avg1, _ = report1[action]['avg per 1000 docs']
        total2, _ = report2[action]['total']
        avg2, _ = report2[action]['avg per 1000 docs']
        assert total1 > 0
        assert avg1 > 0
        assert total2 > 0
        assert avg2 > 0

    # Benchmark components are designed to guarantee at least 1 hit per
    # search term and facet term. With combos of search terms and facet
    # terms, you may have runs where you get 0 search term hits. But if
    # you are including "blank" (i.e. *:*) then THAT should produce
    # your 1 hit (on low cardinality facet values).
    blank_avgs1 = []
    allterms_avgs1 = []
    blank_avgs2 = []
    allterms_avgs2 = []
    for label in search_labels:
        blank_avg1, _ = report1['SEARCH']['BLANK'][label]
        blank_avgs1.append(blank_avg1)
        allterms_avg1, _ = report1['SEARCH']['ALL TERMS'][label]
        allterms_avgs1.append(allterms_avg1)
        blank_avg2, _ = report2['SEARCH']['BLANK'][label]
        blank_avgs2.append(blank_avg2)
        allterms_avg2, _ = report2['SEARCH']['ALL TERMS'][label]
        allterms_avgs2.append(allterms_avg2)
        if label in search_run_defs:
            res1 = s_stats1[label]['term_results']
            res2 = s_stats2[label]['term_results']
            assert any(tr1['hits'] > 0 for tr1 in res1)
            assert all(
                tr1['hits'] == tr2['hits'] for tr1, tr2 in zip(res1, res2)
            )
    # Timings for a search run may average to 0 when dealing with very
    # low numbers of results (such as in these tests). We just want to
    # make sure SOMETHING returned a >0 timing.
    assert any(avg > 0 for avg in blank_avgs1)
    assert any(avg > 0 for avg in allterms_avgs2)
    assert any(avg > 0 for avg in blank_avgs2)
    assert any(avg > 0 for avg in allterms_avgs2)
