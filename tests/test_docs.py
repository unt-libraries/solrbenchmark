"""Contains tests for `docs` module."""
import pytest

from solrbenchmark import docs


# Fixtures & Test Data

@pytest.fixture
def fileset_check():
    """Fixture: returns a func to check FileSet state."""
    def _fileset_check(fset, termsfile_exists=False, docsfile_exists=False,
                       exp_search=None, exp_facet=None, exp_docs=None):
        assert fset.terms_filepath.exists() == termsfile_exists
        assert fset.docs_filepath.exists() == docsfile_exists
        assert fset.search_terms == exp_search
        assert fset.facet_terms == exp_facet
        assert list(fset.docs) == [] if exp_docs is None else exp_docs
    return _fileset_check


@pytest.fixture
def testdocset_check():
    """Fixture: returns a func to check TestDocSet state."""
    def _testdocset_check(docset, exp_search=None, exp_facet=None,
                          exp_docs=None, exp_total_docs=0, exp_facet_counts={},
                          exp_facet_counts_with_vals={}):
        if exp_search is not None:
            assert docset.search_terms == exp_search
        if exp_facet is not None:
            assert docset.facet_terms == exp_facet
        if exp_docs is not None:
            assert list(docset.docs) == exp_docs
        assert docset.total_docs == exp_total_docs
        assert docset.facet_counts == exp_facet_counts
        assert docset.facet_counts_with_vals == exp_facet_counts_with_vals
    return _testdocset_check


# Note: built-in pytest fixture `tmpdir` is used throughout tests. This
# creates a unique temporary directory for each test instance, so that
# FileSet objects can save / load files. This means each test starts
# with a clean slate, and files do NOT persist between tests.
#
# In addition, a few of the tests use the `simple_schema` pytest
# fixture defined in the `conftest.py` file.


# Tests

def test_fileset_get_nonexistent_terms_and_docs(tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_nonexistent_terms')
    fileset_check(fset, termsfile_exists=False, docsfile_exists=False,
                  exp_search=None, exp_facet=None, exp_docs=None)


def test_fileset_filepaths(tmpdir):
    fset = docs.FileSet(tmpdir, 'testing_filenames')
    assert fset.terms_filepath == tmpdir / 'testing_filenames_terms.json'
    assert fset.docs_filepath == tmpdir / 'testing_filenames_docs.json'


@pytest.mark.parametrize('search, facet', [
    (None, None),
    (['search1', 'search2'], None),
    (None, {'test_facet': ['one', 'two']}),
    (['search1', 'search2'], {'test_facet': ['one', 'two']}),
])
def test_fileset_create_terms(search, facet, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_create_terms')
    fset.save_terms(search, facet)
    fileset_check(fset, termsfile_exists=True, exp_search=search,
                  exp_facet=facet)


@pytest.mark.parametrize('search, facet', [
    (None, None),
    (['search1', 'search2'], None),
    (None, {'test_facet': ['one', 'two']}),
    (['search1', 'search2'], {'test_facet': ['one', 'two']}),
])
def test_fileset_get_saved_terms(search, facet, tmpdir, fileset_check):
    fset = docs.FileSet(tmpdir, 'testing_saved_terms')
    fset.save_terms(search, facet)
    del(fset)
    load_fset = docs.FileSet(tmpdir, 'testing_saved_terms')
    fileset_check(load_fset, termsfile_exists=True, exp_search=search,
                  exp_facet=facet)


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
    fset_id = 'testing_saving_and_overwriting_terms'
    fset = docs.FileSet(tmpdir, fset_id)
    fset.save_terms(old_search, old_facet)
    del(fset)

    # Then we load the fileset with that ID, make sure the old terms
    # were saved, and save a new set of terms.
    loaded_base_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_base_fset, termsfile_exists=True,
                  exp_search=old_search, exp_facet=old_facet)
    loaded_base_fset.save_terms(new_search, new_facet)
    del(loaded_base_fset)

    # Finally, for good measure, we load up a third FileSet using that
    # ID to check and make sure we're loading the new terms.
    loaded_changed_fset = docs.FileSet(tmpdir, fset_id)
    exp_new_search = old_search if new_search is None else new_search
    exp_new_facet = old_facet if new_facet is None else new_facet
    fileset_check(loaded_changed_fset, termsfile_exists=True,
                  exp_search=exp_new_search, exp_facet=exp_new_facet)


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
    fileset_check(fset, docsfile_exists=True, exp_docs=test_docs)


def test_fileset_get_saved_docs(tmpdir, fileset_check):
    fset_id = 'testing_saving_docs'
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    fset = docs.FileSet(tmpdir, fset_id)
    _ = list(fset.stream_docs_to_file(test_docs))
    del(fset)
    loaded_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_fset, docsfile_exists=True, exp_docs=test_docs)


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
    fset_id = 'testing_saving_then_overwriting_docs'
    old_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    new_docs = [{'id': 3, 'title': 'Test Doc 3', 'tags': None}]

    # First create the original base file with the old docset.
    fset = docs.FileSet(tmpdir, fset_id)
    _ = list(fset.stream_docs_to_file(old_docs))
    del(fset)

    # Then load that into a new FileSet object, check it, and then
    # stream the new docset, using overwrite=True.
    loaded_base_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_base_fset, docsfile_exists=True, exp_docs=old_docs)
    _ = list(loaded_base_fset.stream_docs_to_file(new_docs, overwrite=True))
    del(loaded_base_fset)

    # Finally, load the same fset_id into a new FileSet object and make
    # sure the new docset was saved.
    loaded_changed_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_changed_fset, docsfile_exists=True, exp_docs=new_docs)


def test_fileset_save_then_append_docs(tmpdir, fileset_check):
    # Saving docs to a file and then streaming new docs to that file
    # with `overwrite` set to False should append the new docs to the
    # file.
    fset_id = 'testing_saving_then_appending_docs'
    old_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    new_docs = [{'id': 3, 'title': 'Test Doc 3', 'tags': None}]

    # First create the original base file with the old docset.
    fset = docs.FileSet(tmpdir, fset_id)
    _ = list(fset.stream_docs_to_file(old_docs))
    del(fset)

    # Then load that into a new FileSet object, confirm the old docset
    # is there, and stream the new docset using overwrite=False.
    loaded_base_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_base_fset, docsfile_exists=True, exp_docs=old_docs)
    _ = list(loaded_base_fset.stream_docs_to_file(new_docs, overwrite=False))
    del(loaded_base_fset)

    # Finally, load that fset_id into a new FileSet object and make
    # sure the saved docset is the old one + the new one.
    loaded_changed_fset = docs.FileSet(tmpdir, fset_id)
    exp = old_docs + new_docs
    fileset_check(loaded_changed_fset, docsfile_exists=True, exp_docs=exp)


def test_fileset_clear_files(tmpdir, fileset_check):
    # The `clear` method should fully clear all FileSet data and delete
    # the underlying files.
    fset_id = 'testing_clearing_files'
    test_docs = [{'id': 1, 'title': 'Test Doc 1', 'tags': ['one', 'two']},
                 {'id': 2, 'title': 'Test Doc 2', 'tags': None}]
    search_terms = ['one', 'two']
    facet_terms = {'test_facet': ['one', 'two', 'three']}
    fset = docs.FileSet(tmpdir, fset_id)
    fset.save_terms(search_terms, facet_terms)
    _ = list(fset.stream_docs_to_file(test_docs))
    fset.clear()
    fileset_check(fset, termsfile_exists=False, docsfile_exists=False,
                  exp_search=None, exp_facet=None, exp_docs=None)


def test_fileset_multiple_different_filesets_at_once(tmpdir, fileset_check):
    # Filesets are identified by their basepath and id; you can have
    # different filesets at one time at the same basepath, provided
    # they have different ids. They will not conflict.
    fset_defs = [
        ('first', ['one', 'two'], {'colors': ['red', 'green', 'yellow']},
         [{'id': 1, 'title': 'Test Doc 1'}, {'id': 2, 'title': 'Test Doc 2'}]),
        ('second', ['three'], {'cars': ['sedan', 'truck'], 'animals': ['cat']},
         [{'id': 3, 'title': 'Test Doc 3'}])
    ]

    # First create / save each different FileSet.
    for fset_id, sterms, fterms, tdocs in fset_defs:
        fset = docs.FileSet(tmpdir, fset_id)
        fset.save_terms(sterms, fterms)
        _ = list(fset.stream_docs_to_file(tdocs))
        fileset_check(fset, termsfile_exists=True, docsfile_exists=True,
                      exp_search = sterms, exp_facet=fterms, exp_docs=tdocs)
        del(fset)

    # Then load each FileSet and check to make sure it contains the
    # expected data.
    for fset_id, sterms, fterms, tdocs in fset_defs:
        fset = docs.FileSet(tmpdir, fset_id)
        fileset_check(fset, termsfile_exists=True, docsfile_exists=True,
                      exp_search = sterms, exp_facet=fterms, exp_docs=tdocs)


def test_testdocset_init(testdocset_check):
    sterms = ['one', 'two']
    fterms = {'colors': ['red', 'blue', 'green']}
    test_docs = [{'id': 1, 'title': 'Test 1'}, {'id': 2, 'title': 'Test 2'}]
    docset = docs.TestDocSet(sterms, fterms, test_docs)
    # At this stage we don't check docset.docs, because iterating
    # through the `docs` attribute populates facet counts, etc.
    testdocset_check(docset, exp_search=sterms, exp_facet=fterms,
                     exp_total_docs=0, exp_facet_counts={'colors': []},
                     exp_facet_counts_with_vals={'colors': []})


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
      {'id': 5, 'title': 'Test 5', 'colors': ['red'],},
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
def test_testdocset_facet_counts(fterms, test_docs, exp_fcounts,
                                 exp_fcounts_vals, testdocset_check):
    sterms = ['one', 'two']
    docset = docs.TestDocSet(sterms, fterms, test_docs)
    testdocset_check(docset, exp_facet=fterms, exp_docs=test_docs,
                     exp_total_docs=len(test_docs),
                     exp_facet_counts=exp_fcounts,
                     exp_facet_counts_with_vals=exp_fcounts_vals)


def test_testdocset_docs_from_generator(testdocset_check):
    # TestDocSet is designed to be able to use a generator for `docs`.
    docgen = ({'id': i, 'title': f'Test {i}', 'test': 'one'} for i in range(3))
    exp_docs = [{'id': 0, 'title': 'Test 0', 'test': 'one'},
                {'id': 1, 'title': 'Test 1', 'test': 'one'},
                {'id': 2, 'title': 'Test 2', 'test': 'one'}]
    docset = docs.TestDocSet(['one', 'two'], {'test': ['one', 'two']}, docgen)
    testdocset_check(docset, exp_docs=exp_docs, exp_total_docs=3,
                     exp_facet_counts={'test': [3]},
                     exp_facet_counts_with_vals={'test': [('one', 3)]})


def test_testdocset_fromschema_no_fileset(testdocset_check, simple_schema):
    # Creating a TestDocSet from a schema (e.g. BenchmarkSchema) should
    # use the schema definition to generate docs, search terms, facet
    # values, etc. This should work whether the 'fileset' argument is
    # used or not.
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
    exp_fcounts = {
        'colors': [1, 1, 1, 1, 1, 1, 1],
        'pattern': [1, 1, 1, 1, 1]
    }
    exp_fcounts_vals = {
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
    docset = docs.TestDocSet.from_schema(myschema)
    testdocset_check(docset, exp_docs=exp_docs, exp_total_docs=5,
                     exp_facet_counts=exp_fcounts,
                     exp_facet_counts_with_vals=exp_fcounts_vals)


def test_testdocset_fromschema_w_fileset(tmpdir, fileset_check, simple_schema):
    # Creating a TestDocSet from a schema (e.g. BenchmarkSchema) AND
    # using the 'fileset' argument should stream / save docs to disk
    # via the given FileSet object.
    fset_id = 'testing_testdocset_fromschema'
    fset = docs.FileSet(tmpdir, fset_id)
    myschema = simple_schema(5, 0.5, 0.5, 999)
    docset = docs.TestDocSet.from_schema(myschema, fileset=fset)
    exp_docs = list(docset.docs)
    del(fset)
    loaded_fset = docs.FileSet(tmpdir, fset_id)
    fileset_check(loaded_fset, termsfile_exists=True, docsfile_exists=True,
                  exp_search=docset.search_terms, exp_facet=docset.facet_terms,
                  exp_docs=exp_docs)


def test_testdocset_fromfileset(tmpdir, testdocset_check):
    # Creating a TestDocSet from a saved FileSet should build/rebuild
    # that docset as expected.
    sterms = ['one', 'two']
    fterms = {'colors': ['red', 'blue', 'green', 'yellow']}
    test_docs = [
        {'id': 1, 'title': 'Test 1', 'colors': ['red', 'yellow']},
        {'id': 2, 'title': 'Test 2', 'colors': ['red', 'blue']},
        {'id': 3, 'title': 'Test 3', 'colors': ['green']}
    ]
    exp_fcounts = {'colors': [2, 1, 1, 1]}
    exp_fcounts_vals = {'colors': [('red', 2), ('yellow', 1), ('blue', 1),
                                   ('green', 1)]}
    fset = docs.FileSet(tmpdir, 'testing_testdocset_fromfileset')
    fset.save_terms(sterms, fterms)
    _ = list(fset.stream_docs_to_file(test_docs))
    docset = docs.TestDocSet.from_fileset(fset)
    testdocset_check(docset, exp_search=sterms, exp_facet=fterms,
                     exp_docs=test_docs, exp_total_docs=3,
                     exp_facet_counts=exp_fcounts,
                     exp_facet_counts_with_vals=exp_fcounts_vals)
