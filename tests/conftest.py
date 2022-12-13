"""Contains pytest configuration."""
import pytest
from fauxdoc.emitters.choice import chance, Choice
from fauxdoc.emitters.fixed import Iterative, Sequential
from fauxdoc.emitters.fromfields import CopyFields
from fauxdoc.profile import Field

from solrbenchmark import schema, runner


LETTERS = 'abcdefghijklmnopqrstuvwxyz'


@pytest.fixture
def term_selection_sanity_check():
    """Fixture: returns a func for sanity checking term selection.

    When selecting from a set of search or facet terms, each available
    term should be selected once before repetition happens. (This is
    what the terms.TermChoice emitter should accomplish.) So:
        - If the number of output values >= the number of available
          terms, the set of output values should match the set of
          available terms. (E.g. all available terms and only available
          terms should be in the output.)
        - If there are fewer output values than available terms, then
          all output terms must be unique and there must not be any
          output terms that aren't in the set of available terms.
    """
    def _term_selection_sanity_check(output, available_terms,
                                     term_exact_match):
        if term_exact_match:
            found = output
        else:
            found = [t for v in output for t in available_terms if t in v]
        output_terms = set(found)
        num_output_values = len(found)
        num_output_terms = len(output_terms)
        num_available_terms = len(available_terms)
        available_terms = set(available_terms)
        if num_output_values >= num_available_terms:
            assert output_terms == available_terms
        else:
            assert num_output_terms == num_output_values
            assert output_terms - available_terms == set()
    return _term_selection_sanity_check


@pytest.fixture
def vocabulary_sanity_check():
    """Fixture: returns a func for sanity checking vocab terms.

    Search and facet vocabularies that are generated should have the
    following qualities.
        - Each term should each be unique.
        - There should be `vocab_size` number of terms.
    """
    def _vocabulary_sanity_check(vocab_terms, vocab_size):
        assert len(set(vocab_terms)) == len(vocab_terms) == vocab_size
    return _vocabulary_sanity_check


@pytest.fixture
def phrases_sanity_check():
    """Fixture: returns a func for sanity checking generated phrases.

    Sets of phrases generated to embed as search terms should have the
    following qualities.
        - `phrase_counts` should provide a list of how many 2-word
          3-word, 4-word, etc. phrases that the generated phrases
          should contain.
        - Each phrase should be unique.
        - The total number of unique phrases should match the sum of
          all counts in `phrase_counts`.
    """
    def _phrases_sanity_check(sterms, phrase_counts):
        tlen_counts = {}
        for term in sterms:
            key = len(term.split(' ')) - 2
            tlen_counts[key] = tlen_counts.get(key, 0) + 1
        for index in sorted(tlen_counts):
            assert phrase_counts[index] == tlen_counts[index]
        assert sum(phrase_counts) == len(sterms) == len(set(sterms))
    return _phrases_sanity_check


@pytest.fixture
def simple_schema():
    """Fixture: returns a func that generates a simple BenchmarkSchema.

    This is only used in tests that don't test BenchmarkSchema
    directly.
    """
    colors = ['red', 'yellow', 'black', 'orange', 'green', 'white', 'blue',
              'grey', 'brown', 'purple']
    patterns = ['paisley', 'striped', 'checkered', 'plaid', 'solid']

    def _simple_schema(numdocs, inject_chance, overwrite_chance, seed):
        myschema = schema.BenchmarkSchema(
            Field(
                'id',
                Iterative(lambda: (f"{n:07d}" for n in range(1, 1000000)))
            ),
            Field(
                'title',
                Iterative(lambda: (f"Test Doc {n}" for n in range(1, 1000000)))
            ),
            schema.FacetField(
                'colors', Choice(colors), repeat=Choice(range(1, 4)),
                gate=chance(0.66),
                cardinality_function=schema.static_cardinality(len(colors))
            ),
            schema.FacetField(
                'pattern', Choice(patterns),
                cardinality_function=schema.static_cardinality(len(patterns))
            )
        )
        myschema.add_fields(
            schema.SearchField(
                'title_search',
                CopyFields(myschema.fields['title'])
            ),
            schema.SearchField(
                'colors_search',
                CopyFields(myschema.fields['colors']),
            ),
            schema.SearchField(
                'pattern_search',
                CopyFields(myschema.fields['pattern'])
            )
        )
        sterm_emitter = Sequential([f"_{v * 3}_" for v in LETTERS])
        myschema.configure(numdocs, sterm_emitter, inject_chance,
                           overwrite_chance, seed)
        return myschema
    return _simple_schema


@pytest.fixture
def configdata():
    """Fixture: returns a throw-away runner.ConfigData object."""
    return runner.ConfigData(
        config_id='test-config',
        solr_version='8.11.1',
        solr_caches='default',
        solr_conf='default barebones test conf',
        solr_schema='test_core schema',
        os='docker-solr',
        os_memory='2GB',
        jvm_memory='-Xmx250M',
        jvm_settings='default',
        collection_size='1MB',
        notes='this is just for illustration purposes'
    )


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
