"""Make sets of documents for Solr benchmarking."""
from pathlib import Path

import ujson


def compose_terms_json_filepath(basepath, docset_id):
    """Get the full filepath to a 'terms' json file for a docset."""
    return Path(basepath) / f'{docset_id}_terms.json'


def compose_docs_json_filepath(basepath, docset_id):
    """Get the full filepath to a 'docs' json file for a docset."""
    return Path(basepath) / f'{docset_id}_docs.json'


def compose_counts_json_filepath(basepath, docset_id):
    """Get the full filepath to a 'counts' json file for a docset."""
    return Path(basepath) / f'{docset_id}_counts.json'


def _is_file_empty(filepath):
    """Returns True if a file is empty or does not exist."""
    try:
        fh = filepath.open('r')
    except FileNotFoundError:
        return True
    with fh:
        return not bool(fh.readline())


def _get_data(fpath):
    """Gets JSON data from a filepath and returns a dict."""
    try:
        fh = fpath.open('r')
    except FileNotFoundError:
        return {}
    with fh:
        try:
            return ujson.loads(fh.read())
        except ujson.JSONDecodeError:
            return {}


def _update_data(fpath, user_data):
    """Updates JSON data at a filepath with the given user_data."""
    data = _get_data(fpath)
    for key, val in user_data.items():
        if val is not None:
            data[key] = val
    with fpath.open('w') as fh:
        fh.write(ujson.dumps(data))
    return data


class FileSet:
    """Class for managing relevant docset files.

    This isn't a private class, but generally end users won't have to
    deal much with FileSet objects on their own. Primarily FileSets are
    generated and used by DocSet instances.
    """
    def __init__(self, basepath, docset_id):
        self._docset_id = docset_id
        self._basepath = Path(basepath)
        self._terms_fpath = compose_terms_json_filepath(basepath, docset_id)
        self._docs_fpath = compose_docs_json_filepath(basepath, docset_id)
        self._counts_fpath = compose_counts_json_filepath(basepath, docset_id)
        self._search_terms = None
        self._facet_terms = None
        self._total_docs = None
        self._facet_value_counts = None

    @property
    def docset_id(self):
        return self._docset_id

    @property
    def basepath(self):
        return self._basepath

    @property
    def terms_filepath(self):
        return self._terms_fpath

    @property
    def docs_filepath(self):
        return self._docs_fpath

    @property
    def counts_filepath(self):
        return self._counts_fpath

    @property
    def filepaths(self):
        return [self._terms_fpath, self._docs_fpath, self._counts_fpath]

    @property
    def terms_file_empty(self):
        return _is_file_empty(self._terms_fpath)

    @property
    def docs_file_empty(self):
        return _is_file_empty(self._docs_fpath)

    @property
    def counts_file_empty(self):
        return _is_file_empty(self._counts_fpath)

    @property
    def search_terms(self):
        if self._search_terms is None:
            self._refresh_terms()
        return self._search_terms

    @property
    def facet_terms(self):
        if self._facet_terms is None:
            self._refresh_terms()
        return self._facet_terms

    @property
    def total_docs(self):
        if self._total_docs is None:
            self._refresh_counts()
        return self._total_docs

    @property
    def facet_value_counts(self):
        if self._facet_value_counts is None:
            self._refresh_counts()
        return self._facet_value_counts

    @property
    def docs(self):
        try:
            fh = self._docs_fpath.open('r')
        except FileNotFoundError:
            return iter([])
        with fh:
            for jsonline in fh:
                yield ujson.loads(jsonline)

    def _refresh_terms(self, data=None):
        data = data or _get_data(self._terms_fpath)
        self._search_terms = data.get('search_terms')
        self._facet_terms = data.get('facet_terms')

    def _refresh_counts(self, data=None):
        data = data or _get_data(self._counts_fpath)
        self._total_docs = data.get('total_docs')
        self._facet_value_counts = data.get('facet_value_counts')

    def save_terms(self, search_terms=None, facet_terms=None):
        """Saves sets of search or facet terms to disk.

        If an argument is None, the existing values for that item are
        left alone -- i.e., you can update only one or the other, if
        you wish.
        """
        data = _update_data(self._terms_fpath, {
            'search_terms': search_terms,
            'facet_terms': facet_terms
        })
        self._refresh_terms(data)

    def save_counts(self, total_docs=None, facet_value_counts=None):
        """Saves total_docs or facet_value_counts to disk.

        If an argument is None, the existing values for that item are
        left alone -- i.e., you can update only one or the other, if
        you wish.
        """
        data = _update_data(self._counts_fpath, {
            'total_docs': total_docs,
            'facet_value_counts': facet_value_counts
        })
        self._refresh_counts(data)

    def stream_docs_to_file(self, docs, overwrite=True):
        """Returns a generator that streams each doc to disk.

        Pass an iterable containing the docs you wish to save as the
        'docs' argument. Loop through the returned generator to save
        each doc to disk. If 'overwrite' is False, the existing docs
        file is appended to rather than overwritten.
        """
        mode = 'w' if overwrite else 'a'
        with self._docs_fpath.open(mode) as fh:
            for doc in docs:
                fh.write(f'{ujson.dumps(doc)}\n')
                yield doc

    def clear(self):
        """Clears out this FileSet and deletes the files."""
        self._terms_fpath.unlink(missing_ok=True)
        self._docs_fpath.unlink(missing_ok=True)
        self._counts_fpath.unlink(missing_ok=True)
        self._search_terms = None
        self._facet_terms = None
        self._total_docs = None
        self._facet_value_counts = None


class SchemaToFileSetLikeAdapter:
    """Class that adapts a BenchmarkSchema instance for DocSet use.

    Like FileSet, users usually shouldn't have to deal with this class
    directly. Its main purpose is to provide an interface on top of a
    BenchmarkSchema instance so that a DocSet can use it or a FileSet
    instance interchangeably. It provides standard access to the
    underlying docs, search terms, facet terms, and facet value counts.
    It also allows (optionally) saving to a new FileSet.

    Note that, if a FileSet is used, you can force switching between
    read, write, and append behavior using the 'file_action' attribute:
    'r', 'w', or 'a'. By default, for the first run through 'docs', the
    FileSet will be written to (files are overwritten if they already
    exist). For subsequent runs through 'docs', the existing FileSet
    will be read from. If you want a subsequent run to overwrite the
    existing docs file, change 'file_action' to 'w'. Or, if you want to
    append to the existing docs file, change it to 'a'.
    """
    def __init__(self, docset_id, schema, savepath=None):
        """Inits a SchemaToFileSetAdapter instance.

        If 'savepath' is provided, a new FileSet is instantiated and
        saved there. Facet terms, search terms, docs, and facet counts
        are saved there as schema docs are generated. Otherwise, the
        schema docs are not saved.
        """
        self._docset_id = docset_id
        if schema.num_docs is None:
            raise ValueError(
                "The 'schema' argument must be a BenchmarkSchema object that "
                "has been configured (via the `configure` method). The schema "
                "just passed has not been configured."
            )
        self._schema = schema
        facet_fields = schema.facet_fields.values()
        self._facet_terms = {f.name: f.terms for f in facet_fields}
        if savepath is None:
            self._fileset = None
            self.file_action = None
        else:
            self._fileset = FileSet(savepath, docset_id)
            self._fileset.save_terms(self.schema.search_terms,
                                     self._facet_terms)
            self.file_action = 'w'

    def _make_initial_docs_iterator(self):
        self._total_docs = 0
        self._facet_value_counts = {}
        self._facet_value_groups = {}
        self._schema.reset_fields()
        for _ in range(self._schema.num_docs):
            doc = self._schema()
            self._update_tallies(doc)
            yield doc

    def _update_tallies(self, doc):
        self._total_docs += 1
        for fname in self.facet_terms.keys():
            raw = doc.get(fname) or []
            vals = [raw] if not isinstance(raw, (list, tuple)) else raw
            for val in vals:
                fval_group = self._facet_value_groups.get(fname, {})
                fval_group[val] = fval_group.get(val, 0) + 1
                self._facet_value_groups[fname] = fval_group
        if self._total_docs == self.schema.num_docs:
            self._finalize_facet_counts()

    def _finalize_facet_counts(self):
        for fname in self.facet_terms.keys():
            fval_group = self._facet_value_groups.get(fname, {})
            counts = sorted(list(fval_group.items()), key=lambda x: x[1],
                            reverse=True)
            self._facet_value_counts[fname] = counts
        if self._fileset is not None:
            self._fileset.save_counts(self._total_docs,
                                      self._facet_value_counts)
            self.file_action = 'r'

    @property
    def docset_id(self):
        return self._docset_id

    @property
    def fileset(self):
        return self._fileset

    @property
    def schema(self):
        return self._schema

    @schema.setter
    def schema(self, schema):
        self._reset_fileset()

    @property
    def search_terms(self):
        return self.schema.search_terms

    @property
    def facet_terms(self):
        return self._facet_terms

    @property
    def total_docs(self):
        return self._total_docs

    @property
    def facet_value_counts(self):
        return self._facet_value_counts

    @property
    def docs(self):
        """Returns a new docs iterator.

        The returned iterator functions differently depending on state:
            - If there is no underlying fileset, the schema is reset
              to generate new documents.
            - If the 'file_action' attr is 'w' or 'a', new documents
              are streamed to disk. ('w' overwrites the existing file,
              while 'a' appends to it.)
            - Otherwise, docs from the existing fileset are read and
              returned.
        """
        if self._fileset is None:
            return self._make_initial_docs_iterator()
        if self.file_action in ('w', 'a'):
            overwrite = self.file_action == 'w'
            docs_iter = self._make_initial_docs_iterator()
            return self._fileset.stream_docs_to_file(docs_iter, overwrite)
        return self._fileset.docs


class DocSet:
    """Class for managing sets of test documents.

    To use:
        - If you are creating a new DocSet from a schema, use the
          `from_schema` factory method. Provide a 'savepath' argument
          to save the DocSet to disk for later reuse.
        - If you are importing a previously saved DocSet, use the
          `from_disk` factory method to load a DocSet from disk.
        - Iterate through the docset.docs property to produce your set
          of documents. Index them into Solr, etc. (You probably want
          to use the `runner` module.) Note that, if you're using a
          schema *without* a savepath, docs are regenerated each time
          you iterate through them.
    """
    def __init__(self, source):
        """Inits a DocSet instance.

        Instead see the `from_schema` and `from_disk` factory methods.
        Likely you want to use one of these to configure the 'source'.
        """
        self.source = source

    @property
    def id(self):
        return self.source.docset_id

    @property
    def search_terms(self):
        return self.source.search_terms

    @property
    def facet_terms(self):
        return self.source.facet_terms

    @property
    def facet_value_counts(self):
        return self.source.facet_value_counts

    @property
    def total_docs(self):
        return self.source.total_docs

    @property
    def fileset(self):
        try:
            self.source.basepath
        except AttributeError:
            return self.source.fileset
        return self.source

    @property
    def docs(self):
        return iter(self.source.docs)

    @classmethod
    def from_schema(cls, docset_id, schema, savepath=None):
        source = SchemaToFileSetLikeAdapter(docset_id, schema, savepath)
        return cls(source)

    @classmethod
    def from_disk(cls, docset_id, loadpath):
        fileset = FileSet(loadpath, docset_id)
        if fileset.terms_file_empty or fileset.docs_file_empty:
            raise FileNotFoundError(
                f'DocSet source files are empty or missing. Expected to find '
                f'"{fileset.terms_filepath}" and "{fileset.docs_filepath}". '
                f'Please check "{fileset.basepath}" and try again.'
            )
        return cls(fileset)
