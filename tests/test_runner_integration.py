"""Contains integration test(s) for `runner` module."""
import pytest

from solrbenchmark import docs, runner


# Fixtures / test data
# Fixtures used here are defined in `conftest.py`:
#    simple_schema
#    solrconn
#    configdata


# Tests

# I've isolated this into a separate test module just because it takes
# several seconds to run.
def test_runner_integration(configdata, simple_schema, solrconn):
    # This is an integration test that tests and illustrates the steps
    # for running benchmark tests from start to finish. Much of the
    # work is done in fixtures, so this is mostly a high-level view.

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

    # THIRD: Set up the system configuration data for your test. This
    # uses a fixture so is glossed over here, but this records details
    # about all the various Solr / system parameters that are under
    # test.
    # E.g.:
    # configdata = runner.ConfigData('config-id', solr_version='8.11', ...)

    # FOURTH: Instantiate a docset (docs.DocSet) and runner
    # (runner.BenchmarkRunner). In reality you'd probably want to save
    # your test docset to disk so you could reproduce the tests later.
    tdocset = docs.DocSet.from_schema('test-docset', myschema, savepath=None)
    trunner = runner.BenchmarkRunner(tdocset, configdata, solrconn)

    # FIFTH: Run the tests. Note how we're using the `search_run_defs`
    # to define and then trigger each of our runs. The labeling there
    # will translate to labeling in the final report.
    i_stats = trunner.index_docs(batch_size=1000, verbose=False)
    s_stats = {
        label: trunner.run_searches(search_terms, label, qargs, 5, 0, False)
        for label, qargs in search_run_defs.items()
    }

    # SIXTH: Compile the final report. In reality, you may also want to
    # save the log to disk to reload it later for further analysis.
    report = trunner.log.compile_report(search_groups)

    # At this point you would want to change your system or Solr
    # configuration (depending on what you're testing), modify the test
    # log metadata to reflect the new configuration, and run through
    # the exact same set of tests again. (This may involve changing the
    # OS memory allocation, changing cache settings, changing Java heap
    # settings, switching schema fields between docValues and inverted
    # fields, or any number of things.) Once you've tested multiple
    # configs you want to compare, you can export each report to a tool
    # or format for comparison and analysis.

    # This last section is for our assertions about stats / reports
    # that were output, to make sure we're getting sane values.
    assert i_stats == trunner.log.indexing_stats
    assert s_stats == trunner.log.search_stats
    assert list(report.keys()) == ['ADD', 'COMMIT', 'INDEXING', 'SEARCH']
    search_labels = list(search_run_defs.keys()) + list(search_groups.keys())
    assert list(report['SEARCH']['BLANK'].keys()) == search_labels
    assert list(report['SEARCH']['ALL TERMS'].keys()) == search_labels

    # With batches of 1000 docs, timings for indexing should all be >0.
    for action in ('ADD', 'COMMIT', 'INDEXING'):
        total, _ = report[action]['total']
        avg, _ = report[action]['avg per 1000 docs']
        assert total > 0
        assert avg > 0

    # Benchmark components are designed to guarantee at least 1 hit per
    # search term and facet term. With combos of search terms and facet
    # terms, you may have runs where you get 0 search term hits. But if
    # you are including "blank" (i.e. *:*) then THAT should produce
    # your 1 hit (on low cardinality facet values).
    blank_avgs = []
    allterms_avgs = []
    for label in search_labels:
        blank_avg, _ = report['SEARCH']['BLANK'][label]
        blank_avgs.append(blank_avg)
        allterms_avg, _ = report['SEARCH']['ALL TERMS'][label]
        allterms_avgs.append(allterms_avg)
        if label in search_run_defs:
            assert any(tr['hits'] > 0 for tr in s_stats[label]['term_results'])
    # Timings for a search run may average to 0 when dealing with very
    # low numbers of results (such as in these tests). We just want to
    # make sure SOMETHING returned a >0 timing.
    assert any(avg > 0 for avg in blank_avgs)
    assert any(avg > 0 for avg in allterms_avgs)
