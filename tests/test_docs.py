"""Contains tests for `docs` module."""
import itertools
from unittest.mock import Mock

import pytest

from solrbenchmark import docs


# Fixtures & Test Data

@pytest.fixture
def facet_value_counts_check():
    """Fixture: returns a func to check facet_value_counts."""
    def _facet_value_counts_check(facet_value_counts, exp_fvcounts):
        if exp_fvcounts is None:
            assert facet_value_counts is None
        else:
            assert facet_value_counts.keys() == exp_fvcounts.keys()
            for fname, counts in facet_value_counts.items():
                exp_counts = exp_fvcounts[fname]
                assert len(counts) == len(exp_counts)
                for actual, expected in zip(counts, exp_counts):
                    assert tuple(actual) == tuple(expected)
    return _facet_value_counts_check


@pytest.fixture
def fileset_check(facet_value_counts_check):
    """Fixture: returns a func to check FileSet state."""
    def _fileset_check(fset, termsfile_exists=False, termsfile_is_empty=True,
                       docsfile_exists=False, docsfile_is_empty=True,
                       countsfile_exists=False, countsfile_is_empty=True,
                       exp_search=None, exp_facet=None, exp_docs=None,
                       exp_tdocs=0, exp_fvcounts=None):
        assert fset.terms_filepath.exists() == termsfile_exists
        assert fset.terms_file_empty == termsfile_is_empty
        assert fset.docs_filepath.exists() == docsfile_exists
        assert fset.docs_file_empty == docsfile_is_empty
        assert fset.counts_filepath.exists() == countsfile_exists
        assert fset.counts_file_empty == countsfile_is_empty
        assert fset.search_terms == exp_search
        assert fset.facet_terms == exp_facet
        assert list(fset.docs) == [] if exp_docs is None else exp_docs
        assert fset.total_docs == exp_tdocs
        facet_value_counts_check(fset.facet_value_counts, exp_fvcounts)
    return _fileset_check


@pytest.fixture
def docset_check(facet_value_counts_check):
    """Fixture: returns a func to check DocSet state."""
    def _docset_check(docset, exp_search=None, exp_facet=None, exp_docs=None,
                      exp_tdocs=0, exp_fvcounts={}):
        if exp_search is not None:
            assert docset.search_terms == exp_search
        if exp_facet is not None:
            assert docset.facet_terms == exp_facet
        if exp_docs is not None:
            assert list(docset.docs) == exp_docs
        assert docset.total_docs == exp_tdocs
        facet_value_counts_check(docset.facet_value_counts, exp_fvcounts)
    return _docset_check


# Note: built-in pytest fixture `tmpdir` is used throughout tests. This
# creates a unique temporary directory for each test instance, so that
# FileSet objects can save / load files. This means each test starts
# with a clean slate, and files do NOT persist between tests.
#
# In addition, a few of the tests use the `simple_schema` pytest
# fixture defined in the `conftest.py` file.


# Tests

def test_fileset_get_nonexistent_data(tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_nonexistent_data')
    fileset_check(fset, termsfile_exists=False, termsfile_is_empty=True,
                  docsfile_exists=False, docsfile_is_empty=True,
                  countsfile_exists=False, countsfile_is_empty=True,
                  exp_search=None, exp_facet=None, exp_docs=None,
                  exp_tdocs=0, exp_fvcounts=None)


def test_fileset_filepaths(tmpdir):
    fset = docs.FileSet(tmpdir, 'testing_filenames')
    assert fset.terms_filepath == tmpdir / 'testing_filenames_terms.json'
    assert fset.docs_filepath == tmpdir / 'testing_filenames_docs.json'
    assert fset.counts_filepath == tmpdir / 'testing_filenames_counts.json'


@pytest.mark.parametrize('search, facet', [
    (None, None),
    (['search1', 'search2'], None),
    (None, {'test_facet': ['one', 'two']}),
    (['search1', 'search2'], {'test_facet': ['one', 'two']}),
])
def test_fileset_create_terms(search, facet, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_create_terms')
    fset.save_terms(search, facet)
    fileset_check(fset, termsfile_exists=True, termsfile_is_empty=False,
                  exp_search=search, exp_facet=facet)


@pytest.mark.parametrize('search, facet', [
    (None, None),
    (['search1', 'search2'], None),
    (None, {'test_facet': ['one', 'two']}),
    (['search1', 'search2'], {'test_facet': ['one', 'two']}),
])
def test_fileset_get_saved_terms(search, facet, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_saved_terms')
    fset.save_terms(search, facet)
    del fset
    load_fset = docs.FileSet(tmpdir, 'testing_saved_terms')
    fileset_check(load_fset, termsfile_exists=True, termsfile_is_empty=False,
                  exp_search=search, exp_facet=facet)


@pytest.mark.parametrize('tdocs, fv_counts', [
    (0, None),
    (100, None),
    (0, {'colors': [('red', 1), ('blue', 1)]}),
    (100, {'colors': [('red', 1), ('blue', 1)]}),
])
def test_fileset_create_counts(tdocs, fv_counts, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_create_counts')
    fset.save_counts(tdocs, fv_counts)
    fileset_check(fset, countsfile_exists=True, countsfile_is_empty=False,
                  exp_tdocs=tdocs, exp_fvcounts=fv_counts)


@pytest.mark.parametrize('tdocs, fv_counts', [
    (0, None),
    (100, None),
    (0, {'colors': [('red', 1), ('blue', 1)]}),
    (100, {'colors': [('red', 1), ('blue', 1)]}),
])
def test_fileset_get_saved_counts(tdocs, fv_counts, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_saved_counts')
    fset.save_counts(tdocs, fv_counts)
    del fset
    load_fset = docs.FileSet(tmpdir, 'testing_saved_counts')
    fileset_check(load_fset, countsfile_exists=True, countsfile_is_empty=False,
                  exp_tdocs=tdocs, exp_fvcounts=fv_counts)


@pytest.mark.parametrize('old_search, old_facet, new_search, new_facet', [
    (None, None, ['new_search1', 'new_search2'],
     {'animals': ['cats', 'birds', 'dogs', 'zebras']}),
    (['old_search1', 'old_search2'],
     {'colors': ['red', 'blue', 'green'],
      'boats': ['sailboats', 'rowboats', 'battleships']}, None, None),
    (['old_search1', 'old_search2'], None,
     ['new_search1', 'new_search2'], None),
    (None,
     {'colors': ['red', 'blue', 'green'],
      'boats': ['sailboats', 'rowboats', 'battleships']},
     ['new_search1', 'new_search2'], None),
    (['old_search1', 'old_search2'],
     {'colors': ['red', 'blue', 'green'],
      'boats': ['sailboats', 'rowboats', 'battleships']},
     ['new_search1', 'new_search2'], None),
    (['old_search1', 'old_search2'],
     {'colors': ['red', 'blue', 'green'],
      'boats': ['sailboats', 'rowboats', 'battleships']},
     ['new_search1', 'new_search2'],
     {'animals': ['cats', 'birds', 'dogs', 'zebras']}),
    (['old_search1', 'old_search2'],
     {'colors': ['red', 'blue', 'green'],
      'boats': ['sailboats', 'rowboats', 'battleships']}, [], {}),
])
def test_fileset_save_and_overwrite_terms(old_search, old_facet, new_search,
                                          new_facet, tmpdir, fileset_check):
    # Calling `save_terms` should overwrite any existing terms. To test
    # this, first we create a base fileset with terms.
    docset_id = 'testing_saving_and_overwriting_terms'
    fset = docs.FileSet(tmpdir, docset_id)
    fset.save_terms(old_search, old_facet)
    del fset

    # Then we load the fileset with that ID, make sure the old terms
    # were saved, and save a new set of terms.
    loaded_base_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_base_fset, termsfile_exists=True,
                  termsfile_is_empty=False, exp_search=old_search,
                  exp_facet=old_facet)
    loaded_base_fset.save_terms(new_search, new_facet)
    del loaded_base_fset

    # Finally, for good measure, we load up a third FileSet using that
    # ID to check and make sure we're loading the new terms.
    loaded_changed_fset = docs.FileSet(tmpdir, docset_id)
    exp_new_search = old_search if new_search is None else new_search
    exp_new_facet = old_facet if new_facet is None else new_facet
    fileset_check(loaded_changed_fset, termsfile_exists=True,
                  termsfile_is_empty=False, exp_search=exp_new_search,
                  exp_facet=exp_new_facet)


@pytest.mark.parametrize('old_tdocs, old_fvcounts, new_tdocs, new_fvcounts', [
    (0, None, 100, {'colors': [('red', 1), ('blue', 1)]}),
    (5, {'something': [('one', 100)]}, 100,
     {'colors': [('red', 1), ('blue', 1)]}),
    (5, None, 100, None),
    (0, {'colors': [('red', 1), ('blue', 1)]}, 100, None),
    (5, {'something': [('one', 100)]}, 100, None),
    (5, {'something': [('one', 100)]}, 0, {}),
])
def test_fileset_save_and_overwrite_counts(old_tdocs, old_fvcounts, new_tdocs,
                                           new_fvcounts, tmpdir,
                                           fileset_check):
    # Calling `save_counts` should overwrite any existing counts. This
    # test works the same way as the previous test.
    docset_id = 'testing_saving_and_overwriting_counts'
    fset = docs.FileSet(tmpdir, docset_id)
    fset.save_counts(old_tdocs, old_fvcounts)
    del fset

    loaded_base_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_base_fset, countsfile_exists=True,
                  countsfile_is_empty=False, exp_tdocs=old_tdocs,
                  exp_fvcounts=old_fvcounts)
    loaded_base_fset.save_counts(new_tdocs, new_fvcounts)
    del loaded_base_fset

    loaded_changed_fset = docs.FileSet(tmpdir, docset_id)
    exp_new_tdocs = old_tdocs if new_tdocs is None else new_tdocs
    exp_new_fvcounts = old_fvcounts if new_fvcounts is None else new_fvcounts
    fileset_check(loaded_changed_fset, countsfile_exists=True,
                  countsfile_is_empty=False, exp_tdocs=exp_new_tdocs,
                  exp_fvcounts=exp_new_fvcounts)


@pytest.mark.parametrize('overwrite', [
    True,
    False
])
def test_fileset_create_new_docs_file(overwrite, tmpdir, fileset_check):
    # When first saving docs to disk for a new fileset, the `overwrite`
    # parameter can be either True or False, with the same result.
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    fset = docs.FileSet(tmpdir, 'testing_new_docs', )
    streamed = list(fset.stream_docs_to_file(test_docs, overwrite=overwrite))
    assert streamed == test_docs
    fileset_check(fset, docsfile_exists=True, docsfile_is_empty=False,
                  exp_docs=test_docs)


def test_fileset_get_saved_docs(tmpdir, fileset_check):
    docset_id = 'testing_saving_docs'
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    fset = docs.FileSet(tmpdir, docset_id)
    _ = list(fset.stream_docs_to_file(test_docs))
    del fset
    loaded_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_fset, docsfile_exists=True, docsfile_is_empty=False,
                  exp_docs=test_docs)


def test_fileset_access_docs_during_streaming(tmpdir):
    # Attempting to access a fileset's docs while in the middle of
    # streaming new docs to disk should not create a conflict. Each
    # time you access the `docs` attribute, it gives you a new
    # generator that iterates through whatever docs have been saved up
    # to that point.
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None},
                 {'id': 3, 'title': 'Test Doc 3', 'tags': None}]
    fset = docs.FileSet(tmpdir, 'testing_docs_access_during_streaming')
    expected = []
    for in_doc in fset.stream_docs_to_file(test_docs):
        expected.append(in_doc)
        for out_doc in fset.docs:
            assert out_doc in expected


def test_fileset_save_then_overwrite_docs(tmpdir, fileset_check):
    # Saving docs to a file and then streaming new docs to that file
    # with `overwrite` set to True should overwrite the saved docs.
    docset_id = 'testing_saving_then_overwriting_docs'
    old_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    new_docs = [{'id': 3, 'title': 'Test Doc 3', 'tags': None}]

    # First create the original base file with the old docset.
    fset = docs.FileSet(tmpdir, docset_id)
    _ = list(fset.stream_docs_to_file(old_docs))
    del fset

    # Then load that into a new FileSet object, check it, and then
    # stream the new docset, using overwrite=True.
    loaded_base_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_base_fset, docsfile_exists=True,
                  docsfile_is_empty=False, exp_docs=old_docs)
    _ = list(loaded_base_fset.stream_docs_to_file(new_docs, overwrite=True))
    del loaded_base_fset

    # Finally, load the same docset_id into a new FileSet object and make
    # sure the new docset was saved.
    loaded_changed_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_changed_fset, docsfile_exists=True,
                  docsfile_is_empty=False, exp_docs=new_docs)


def test_fileset_save_then_append_docs(tmpdir, fileset_check):
    # Saving docs to a file and then streaming new docs to that file
    # with `overwrite` set to False should append the new docs to the
    # file.
    docset_id = 'testing_saving_then_appending_docs'
    old_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    new_docs = [{'id': 3, 'title': 'Test Doc 3', 'tags': None}]

    # First create the original base file with the old docset.
    fset = docs.FileSet(tmpdir, docset_id)
    _ = list(fset.stream_docs_to_file(old_docs))
    del fset

    # Then load that into a new FileSet object, confirm the old docset
    # is there, and stream the new docset using overwrite=False.
    loaded_base_fset = docs.FileSet(tmpdir, docset_id)
    fileset_check(loaded_base_fset, docsfile_exists=True,
                  docsfile_is_empty=False, exp_docs=old_docs)
    _ = list(loaded_base_fset.stream_docs_to_file(new_docs, overwrite=False))
    del loaded_base_fset

    # Finally, load that docset_id into a new FileSet object and make
    # sure the saved docset is the old one + the new one.
    loaded_changed_fset = docs.FileSet(tmpdir, docset_id)
    exp = old_docs + new_docs
    fileset_check(loaded_changed_fset, docsfile_exists=True,
                  docsfile_is_empty=False, exp_docs=exp)


def test_fileset_clear_files(tmpdir, fileset_check):
    # The `clear` method should fully clear all FileSet data and delete
    # the underlying files.
    docset_id = 'testing_clearing_files'
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    search_terms = ['one', 'two']
    facet_terms = {'test_facet': ['one', 'two', 'three']}
    tdocs = 2
    fv_counts = {'tags': [('one', 1), ('two', 2)]}
    fset = docs.FileSet(tmpdir, docset_id)
    fset.save_terms(search_terms, facet_terms)
    fset.save_counts(tdocs, fv_counts)
    _ = list(fset.stream_docs_to_file(test_docs))
    fset.clear()
    fileset_check(fset, termsfile_exists=False, termsfile_is_empty=True,
                  docsfile_exists=False, docsfile_is_empty=True,
                  countsfile_exists=False, countsfile_is_empty=True,
                  exp_search=None, exp_facet=None, exp_docs=None,
                  exp_tdocs=0, exp_fvcounts=None)


def test_fileset_clear_nonexistent_files(tmpdir, fileset_check):
    # If `clear` is called but files do not yet exist, no errors should
    # be raised.
    docset_id = 'testing_clearing_nonexistent_files'
    search_terms = ['one', 'two']
    facet_terms = {'test_facet': ['one', 'two', 'three']}
    fset = docs.FileSet(tmpdir, docset_id)
    fset.save_terms(search_terms, facet_terms)
    fset.clear()
    fileset_check(fset, termsfile_exists=False, termsfile_is_empty=True,
                  docsfile_exists=False, docsfile_is_empty=True,
                  countsfile_exists=False, countsfile_is_empty=True,
                  exp_search=None, exp_facet=None, exp_docs=None,
                  exp_tdocs=0, exp_fvcounts=None)


def test_fileset_multiple_different_filesets_at_once(tmpdir, fileset_check):
    # Filesets are identified by their basepath and id; you can have
    # different filesets at one time at the same basepath, provided
    # they have different ids. They will not conflict.
    fset_defs = [
        ('first', ['one', 'two'], {'colors': ['red', 'green', 'yellow']},
         [{'id': 1, 'title': 'Test Doc 1'}, {'id': 2, 'title': 'Test Doc 2'}],
         2, {}),
        ('second', ['three'], {'cars': ['sedan', 'truck'], 'animals': ['cat']},
         [{'id': 3, 'title': 'Test Doc 3'}], 1, {})
    ]

    # First create / save each different FileSet.
    for docset_id, sterms, fterms, testdocs, totdocs, fv_counts in fset_defs:
        fset = docs.FileSet(tmpdir, docset_id)
        fset.save_terms(sterms, fterms)
        fset.save_counts(totdocs, fv_counts)
        _ = list(fset.stream_docs_to_file(testdocs))
        fileset_check(fset, termsfile_exists=True, termsfile_is_empty=False,
                      docsfile_exists=True, docsfile_is_empty=False,
                      countsfile_exists=True, countsfile_is_empty=False,
                      exp_search=sterms, exp_facet=fterms, exp_docs=testdocs,
                      exp_tdocs=totdocs, exp_fvcounts=fv_counts)
        del fset

    # Then load each FileSet and check to make sure it contains the
    # expected data.
    for docset_id, sterms, fterms, testdocs, totdocs, fv_counts in fset_defs:
        fset = docs.FileSet(tmpdir, docset_id)
        fileset_check(fset, termsfile_exists=True, termsfile_is_empty=False,
                      docsfile_exists=True, docsfile_is_empty=False,
                      countsfile_exists=True, countsfile_is_empty=False,
                      exp_search=sterms, exp_facet=fterms, exp_docs=testdocs,
                      exp_tdocs=totdocs, exp_fvcounts=fv_counts)


def test_docset_init(docset_check):
    sterms = ['one', 'two']
    fterms = {'colors': ['red', 'blue', 'green']}
    testdocs = [{'id': 1, 'title': 'Test 1'}, {'id': 2, 'title': 'Test 2'}]
    fv_counts = {'colors': []}
    mock_source_adapter = Mock(
        docset_id='test-docset',
        search_terms=sterms,
        facet_terms=fterms,
        total_docs=2,
        docs=testdocs,
        facet_value_counts=fv_counts
    )
    docset = docs.DocSet(mock_source_adapter)
    docset_check(docset, exp_search=sterms, exp_facet=fterms, exp_tdocs=2,
                 exp_docs=testdocs, exp_fvcounts=fv_counts)


@pytest.mark.parametrize('fterms, test_docs, exp_fcounts, exp_fcounts_vals', [
    ({'colors': ['red', 'blue', 'green']},
     [{'id': 1, 'title': 'Test 1'},
      {'id': 2, 'title': 'Test 2'}],
     {'colors': []}, {'colors': []}),
    ({'colors': ['red', 'blue', 'green', 'yellow']},
     [{'id': 1, 'title': 'Test 1', 'colors': 'red'},
      {'id': 2, 'title': 'Test 2', 'colors': 'green'},
      {'id': 3, 'title': 'Test 3', 'colors': 'green'},
      {'id': 4, 'title': 'Test 4', 'colors': 'green'},
      {'id': 5, 'title': 'Test 5', 'colors': 'red'},
      {'id': 6, 'title': 'Test 6', 'colors': 'blue'}],
     {'colors': [3, 2, 1]},
     {'colors': [('green', 3), ('red', 2), ('blue', 1)]}),
    ({'colors': ['red', 'blue', 'green', 'yellow']},
     [{'id': 1, 'title': 'Test 1', 'colors': ['red', 'yellow', 'blue']},
      {'id': 2, 'title': 'Test 2', 'colors': ['red', 'green']},
      {'id': 3, 'title': 'Test 3', 'colors': 'green'},
      {'id': 4, 'title': 'Test 4', 'colors': ['blue', 'green']},
      {'id': 5, 'title': 'Test 5', 'colors': ['red']},
      {'id': 6, 'title': 'Test 6', 'colors': ['yellow', 'blue', 'red']}],
     {'colors': [4, 3, 3, 2]},
     {'colors': [('red', 4), ('blue', 3), ('green', 3), ('yellow', 2)]}),
    ({'colors': ['red', 'blue', 'green', 'yellow'],
      'pattern': ['striped', 'plaid', 'solid', 'checkered']},
     [{'id': 1, 'title': 'Test 1', 'colors': ['red', 'yellow', 'blue'],
       'pattern': 'plaid'},
      {'id': 2, 'title': 'Test 2', 'colors': ['red', 'green'],
       'pattern': 'striped'},
      {'id': 3, 'title': 'Test 3', 'colors': 'green', 'pattern': 'solid'},
      {'id': 4, 'title': 'Test 4', 'colors': ['blue', 'green'],
       'pattern': 'striped'},
      {'id': 5, 'title': 'Test 5', 'colors': ['red'], 'pattern': 'solid'},
      {'id': 6, 'title': 'Test 6', 'colors': ['yellow', 'blue', 'red'],
       'pattern': 'checkered'}],
     {'colors': [4, 3, 3, 2], 'pattern': [2, 2, 1, 1]},
     {'colors': [('red', 4), ('blue', 3), ('green', 3), ('yellow', 2)],
      'pattern': [('striped', 2), ('solid', 2), ('plaid', 1),
                  ('checkered', 1)]}),

    # The provided facet_terms don't *have* to match up with what's in
    # the doc set (i.e., it still works if they don't). The keys define
    # what the facet fields are, so do need to be there.
    ({'colors': ['Alfred', 'Susan', 'Julie'],
      'pattern': ['happiness', 'melancholy', 'ennui']},
     [{'id': 1, 'title': 'Test 1', 'colors': ['red', 'yellow', 'blue'],
       'pattern': 'plaid'},
      {'id': 2, 'title': 'Test 2', 'colors': ['red', 'green'],
       'pattern': 'striped'}],
     {'colors': [2, 1, 1, 1], 'pattern': [1, 1]},
     {'colors': [('red', 2), ('yellow', 1), ('blue', 1), ('green', 1)],
      'pattern': [('plaid', 1), ('striped', 1)]})
])
def test_schemaadapter_facet_counts(fterms, test_docs, exp_fcounts,
                                    exp_fcounts_vals, docset_check):
    mock_schema = Mock(
        num_docs=len(test_docs),
        facet_fields={
            fn: Mock(terms=terms) for fn, terms in fterms.items()
        },
        search_terms=['one', 'two']
    )
    for fn, mock_field in mock_schema.facet_fields.items():
        mock_field.name = fn
    mock_schema.side_effect = tuple(test_docs)
    adapter = docs.SchemaToFileSetLikeAdapter('test-docset', mock_schema)
    docset = docs.DocSet(adapter)
    docset_check(docset, exp_facet=fterms, exp_docs=test_docs,
                 exp_tdocs=len(test_docs), exp_fvcounts=exp_fcounts_vals)


def test_docset_fromschema_no_savepath_w_rngseed(docset_check, simple_schema):
    # Creating a DocSet from a schema (e.g. BenchmarkSchema) should
    # use the schema definition to generate docs, search terms, facet
    # values, etc. This should work even if 'savepath' is None.
    exp_docs = [
        {'id': '0000001', 'title': 'Test Doc 1', 'colors': None,
         'pattern': 'striped', 'title_search': 'Test Doc 1',
         'colors_search': None, 'pattern_search': 'striped'},
        {'id': '0000002', 'title': 'Test Doc 2',
         'colors': ['green', 'yellow', 'brown'], 'pattern': 'solid',
         'title_search': 'Test Doc _aaa_  2',
         'colors_search': ['green', 'yellow', 'brown'],
         'pattern_search': 'sol _bbb_ id'},
        {'id': '0000003', 'title': 'Test Doc 3', 'colors': None,
         'pattern': 'paisley', 'title_search': 'Test Doc 3',
         'colors_search': None, 'pattern_search': 'paisley'},
        {'id': '0000004', 'title': 'Test Doc 4', 'colors': ['white'],
         'pattern': 'checkered', 'title_search': 'Test  _ccc_ Doc 4',
         'colors_search': ['_ddd_'], 'pattern_search': 'checkered'},
        {'id': '0000005', 'title': 'Test Doc 5',
         'colors': ['grey', 'purple', 'black'], 'pattern': 'plaid',
         'title_search': 'Test Doc 5',
         'colors_search': ['grey', 'purple', 'black'],
         'pattern_search': 'plaid'}
    ]
    exp_fvcounts = {
        'colors': [
            ('green', 1), ('yellow', 1), ('brown', 1), ('white', 1),
            ('grey', 1), ('purple', 1), ('black', 1)
        ],
        'pattern': [
            ('striped', 1), ('solid', 1), ('paisley', 1), ('checkered', 1),
            ('plaid', 1)
        ]
    }
    myschema = simple_schema(5, 0.5, 0.5, 999)
    docset = docs.DocSet.from_schema('test-docset', myschema)
    docset_check(docset, exp_docs=exp_docs, exp_tdocs=5,
                 exp_fvcounts=exp_fvcounts)
    assert docset.fileset is None
    # Attempting to reuse a docset built from a schema with no
    # underlying save file should return additional docs. In this test,
    # because we've set an RNG seed (999), the schema reproduces the
    # same document set each time.
    assert list(docset.docs) == exp_docs
    assert list(docset.docs) == exp_docs


def test_docset_fromschema_no_savepath_no_rngseed(simple_schema):
    myschema = simple_schema(5, 0.5, 0.5, None)
    docset = docs.DocSet.from_schema('test-docset', myschema)
    # Attempting to reuse a docset built from a schema with no
    # underlying save file should return additional docs. In this test,
    # we've used an RNG seed of None (which uses a different RNG seed
    # each time). Each time we call docset.docs, we should get a
    # different set of documents, each of which still conforms to our
    # schema. Also: without an RNG seed, we're dependent on random
    # outcomes; duplicate docsets aren't impossible, just unlikely. To
    # prevent that from causing our test to fail, we'll rerun this test
    # up to ten times to ensure at some point we get different document
    # sets. If ten tries in a row still produces a duplicate document
    # set, then something is probably wrong.
    for _ in range(10):
        results = [list(docset.docs), list(docset.docs), list(docset.docs)]
        exp_ids = ['0000001', '0000002', '0000003', '0000004', '0000005']
        assert all(len(ds) == 5 for ds in results)
        assert all([doc['id'] for doc in ds] == exp_ids for ds in results)
        if all(a != b for a, b in itertools.combinations(results, 2)):
            break
    else:
        pytest.fail(
            'Generating three lists of documents from a docset without using '
            'an RNG seed produced a duplicate docset in each of ten tries. '
            'While this is not impossible, it is HIGHLY unlikely.'
        )


def test_docset_fromschema_w_savepath(tmpdir, fileset_check, simple_schema):
    # Creating a DocSet from a schema (e.g. BenchmarkSchema) AND
    # using the 'savepath' argument should stream / save docs to disk.
    # Also, reusing that same DocSet should subsequently loop through
    # the saved docs rather than generating (and saving) a new docset.
    #
    # In other words: default behavior should be that the schema
    # generates and saves documents on the first pass and reuses them
    # (either from disk or from memory) on subsequent passes, without
    # the user having to specify that behavior.

    # Note: None is used here for the RNG seed to ensure a random set
    # of documents each time the schema is reset. If multiple passes
    # result in the same documents, we know it's loading from disk on
    # subsequent passes.
    myschema = simple_schema(5, 0.5, 0.5, None)
    docset = docs.DocSet.from_schema('test-docset', myschema, savepath=tmpdir)
    results = []
    fv_counts = []
    for _ in range(3):
        results.append(list(docset.docs))
        fv_counts.append(docset.facet_value_counts)

    loaded_fset = docs.FileSet(tmpdir, 'test-docset')
    assert results[0] == results[1] == results[2]
    assert fv_counts[0] == fv_counts[1] == fv_counts[2]
    assert docset.fileset.filepaths == loaded_fset.filepaths
    fileset_check(loaded_fset, termsfile_exists=True, termsfile_is_empty=False,
                  docsfile_exists=True, docsfile_is_empty=False,
                  countsfile_exists=True, countsfile_is_empty=False,
                  exp_search=docset.search_terms, exp_facet=docset.facet_terms,
                  exp_docs=results[0], exp_tdocs=5, exp_fvcounts=fv_counts[0])


def test_docset_fromschema_w_savepath_overwrite(tmpdir, fileset_check,
                                                simple_schema):
    myschema = simple_schema(5, 0.5, 0.5, None)
    docset = docs.DocSet.from_schema('test-docset', myschema, savepath=tmpdir)
    orig_results = list(docset.docs)
    orig_fv_counts = docset.facet_value_counts

    # Part of this test -- comparing randomly-generated document sets
    # to one another -- relies on unseeded RNG to produce results that
    # are likely but not necessarily guaranteed. A docset or set of
    # facet values may accidentally happen to repeat unexpectedly,
    # which would cause assertions to fail. To account for these, we try
    # up to 10 times; it's HIGHLY unlikely to get unexpected repetition
    # 10 times in a row.
    for _ in range(10):
        # When creating a DocSet from a schema and saving results to
        # disk, you can manually set it to write a new set of documents
        # for any subsequent pass, overriding the default behavior of
        # reading from the saved file.
        docset.source.file_action = 'w'
        w_results = list(docset.docs)
        w_fv_counts = docset.facet_value_counts
        if orig_results != w_results and orig_fv_counts != w_fv_counts:
            break
    else:
        pytest.fail(
            'Generating two lists of documents from a docset without using '
            'an RNG seed produced a duplicate list in each of ten tries. '
            'While this is not impossible, it is HIGHLY unlikely.'
        )

    # After manually overriding the default behavior, it will return to
    # the default behavior on the next pass.
    assert w_results == list(docset.docs) == list(docset.docs)
    assert w_fv_counts == docset.facet_value_counts
    loaded_fset = docs.FileSet(tmpdir, 'test-docset')
    assert docset.fileset.filepaths == loaded_fset.filepaths
    fileset_check(loaded_fset, termsfile_exists=True, termsfile_is_empty=False,
                  docsfile_exists=True, docsfile_is_empty=False,
                  countsfile_exists=True, countsfile_is_empty=False,
                  exp_search=docset.search_terms, exp_facet=docset.facet_terms,
                  exp_docs=w_results, exp_tdocs=5, exp_fvcounts=w_fv_counts)


def test_docset_fromschema_w_savepath_append(tmpdir, fileset_check,
                                             simple_schema):
    myschema = simple_schema(5, 0.5, 0.5, None)
    docset = docs.DocSet.from_schema('test-docset', myschema, savepath=tmpdir)
    results = [list(docset.docs)]
    fv_counts = [docset.facet_value_counts]
    # When creating a DocSet from a schema and saving results to disk,
    # you can manually set it to append documents on any subsequent
    # pass, overriding the default behavior of reading from the saved
    # file.
    docset.source.file_action = 'a'
    for _ in range(2):
        results.append(list(docset.docs))
        fv_counts.append(docset.facet_value_counts)
    results.extend([list(docset.docs), list(docset.docs)])
    loaded_fset = docs.FileSet(tmpdir, 'test-docset')
    assert results[2] == results[0] + results[1]
    assert docset.fileset.filepaths == loaded_fset.filepaths
    fileset_check(loaded_fset, termsfile_exists=True, termsfile_is_empty=False,
                  docsfile_exists=True, docsfile_is_empty=False,
                  countsfile_exists=True, countsfile_is_empty=False,
                  exp_search=docset.search_terms, exp_facet=docset.facet_terms,
                  exp_docs=results[2], exp_tdocs=5, exp_fvcounts=fv_counts[2])


def test_docset_fromdisk(tmpdir, docset_check):
    # Creating a DocSet from files saved to disk should build/rebuild
    # that docset as expected. It should also be be possible to reuse
    # that docset as often as needed.
    sterms = ['one', 'two']
    fterms = {'colors': ['red', 'blue', 'green', 'yellow']}
    test_docs = [
        {'id': 1, 'title': 'Test 1', 'colors': ['red', 'yellow']},
        {'id': 2, 'title': 'Test 2', 'colors': ['red', 'blue']},
        {'id': 3, 'title': 'Test 3', 'colors': ['green']}
    ]
    exp_fvcounts = {'colors': [('red', 2), ('yellow', 1), ('blue', 1),
                               ('green', 1)]}
    fset = docs.FileSet(tmpdir, 'test-docset')
    fset.save_terms(sterms, fterms)
    fset.save_counts(3, exp_fvcounts)
    _ = list(fset.stream_docs_to_file(test_docs))
    docset = docs.DocSet.from_disk('test-docset', tmpdir)
    results = [list(docset.docs), list(docset.docs), list(docset.docs)]
    assert results[0] == results[1] == results[2]
    docset_check(docset, exp_search=sterms, exp_facet=fterms,
                 exp_docs=test_docs, exp_tdocs=3, exp_fvcounts=exp_fvcounts)
