"""Contains integration test(s) for `runner` module."""
import pytest

from solrbenchmark import docs, runner


# Fixtures / test data
# 
# Tests below use built-in pytest fixture `tmpdir`. Other fixtures used
# are defined in `conftest.py`:
#    simple_schema
#    solrconn
#    configdata


# Tests

def test_runner_integration(tmpdir, configdata, simple_schema, solrconn):
    # This is an integration test that tests and illustrates the steps
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
        'facet': 'true', 'facet.field': 'colors', 'f.colors.facet.limit': 5,
        'facet.field': 'pattern', 'f.pattern.facet.limit': 5
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
            l for l in search_run_defs if l.startswith('no facets')
        ],
        'all facets GROUP': [
            l for l in search_run_defs if l.startswith('all facets')
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
    trunner = runner.BenchmarkRunner(tdocset, configdata, solrconn)
    i_stats = trunner.index_docs(batch_size=1000)
    s_stats = {
        label: trunner.run_searches(search_terms, label, qargs, 5, 0, False)
        for label, qargs in search_run_defs.items()
    }
    solrconn.delete('*:*', commit=True)
    trunner2 = runner.BenchmarkRunner(tdocset, configdata2, solrconn)
    i_stats2 = trunner2.index_docs(batch_size=1000)
    s_stats2 = {
        label: trunner2.run_searches(search_terms, label, qargs, 5, 0, False)
        for label, qargs in search_run_defs.items()
    }

    # SIXTH: Compile the final report for each test and save it to disk
    # for further analysis later.
    result_file = trunner.log.save_to_json_file(tmpdir)
    report = trunner.log.compile_report(search_groups)
    result_file2 = trunner2.log.save_to_json_file(tmpdir)
    report2 = trunner2.log.compile_report(search_groups)

    # This last section is for our assertions to make sure we're
    # getting sane values for things.
    assert i_stats == trunner.log.indexing_stats
    assert s_stats == trunner.log.search_stats
    assert i_stats2 == trunner2.log.indexing_stats
    assert s_stats2 == trunner2.log.search_stats
    assert list(report.keys()) == ['ADD', 'COMMIT', 'INDEXING', 'SEARCH']
    assert list(report2.keys()) == ['ADD', 'COMMIT', 'INDEXING', 'SEARCH']
    search_labels = list(search_run_defs.keys()) + list(search_groups.keys())
    assert list(report['SEARCH']['BLANK'].keys()) == search_labels
    assert list(report2['SEARCH']['BLANK'].keys()) == search_labels
    assert list(report['SEARCH']['ALL TERMS'].keys()) == search_labels
    assert list(report2['SEARCH']['ALL TERMS'].keys()) == search_labels
    
    filepaths = trunner.docset.fileset.filepaths
    filepaths2 = trunner2.docset.fileset.filepaths
    assert filepaths == filepaths2
    assert all(fp.exists() for fp in filepaths)
    assert result_file.exists()
    assert result_file2.exists()
    assert list(trunner.docset.docs) == list(trunner2.docset.docs)

    # With batches of 1000 docs, timings for indexing should all be >0.
    for action in ('ADD', 'COMMIT', 'INDEXING'):
        total, _ = report[action]['total']
        avg, _ = report[action]['avg per 1000 docs']
        total2, _ = report2[action]['total']
        avg2, _ = report2[action]['avg per 1000 docs']
        assert total > 0
        assert avg > 0
        assert total2 > 0
        assert avg2 > 0

    # Benchmark components are designed to guarantee at least 1 hit per
    # search term and facet term. With combos of search terms and facet
    # terms, you may have runs where you get 0 search term hits. But if
    # you are including "blank" (i.e. *:*) then THAT should produce
    # your 1 hit (on low cardinality facet values).
    blank_avgs = []
    allterms_avgs = []
    blank_avgs2 = []
    allterms_avgs2 = []
    for label in search_labels:
        blank_avg, _ = report['SEARCH']['BLANK'][label]
        blank_avgs.append(blank_avg)
        allterms_avg, _ = report['SEARCH']['ALL TERMS'][label]
        allterms_avgs.append(allterms_avg)
        blank_avg2, _ = report2['SEARCH']['BLANK'][label]
        blank_avgs2.append(blank_avg)
        allterms_avg2, _ = report2['SEARCH']['ALL TERMS'][label]
        allterms_avgs2.append(allterms_avg)
        if label in search_run_defs:
            res = s_stats[label]['term_results']
            res2 = s_stats2[label]['term_results']
            assert any(tr['hits'] > 0 for tr in res)
            assert all(tr['hits'] == tr2['hits'] for tr, tr2 in zip(res, res2))
    # Timings for a search run may average to 0 when dealing with very
    # low numbers of results (such as in these tests). We just want to
    # make sure SOMETHING returned a >0 timing.
    assert any(avg > 0 for avg in blank_avgs)
    assert any(avg > 0 for avg in allterms_avgs)
    assert any(avg > 0 for avg in blank_avgs2)
    assert any(avg > 0 for avg in allterms_avgs2)
