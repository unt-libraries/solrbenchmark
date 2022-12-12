"""Tools for making, saving, and loading sets of documents."""
from pathlib import Path
from typing import (
    Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple,
    Type, TypeVar, Union
)

from solrbenchmark.localtypes import (
    FacetValueCountsArg, FacetValueCountsReturn, PathLike
)
from solrbenchmark.schema import BenchmarkSchema
import ujson


D = TypeVar('D', bound='DocSet')


def compose_terms_json_filepath(basepath: PathLike, docset_id: str) -> Path:
    """Get the full filepath to a 'terms' json file for a docset.

    Args:
        basepath: A str, pathlib.Path, or otherwise os.PathLike object
            representing the base path where the json file lives.
        docset_id: A str that uniquely identifies the docset the terms
            belong to.

    Returns:
        A pathlib.Path object representing the full path to the 'terms'
        json file.
    """
    return Path(basepath) / f'{docset_id}_terms.json'


def compose_docs_json_filepath(basepath: PathLike, docset_id: str) -> Path:
    """Get the full filepath to a 'docs' json file for a docset.

    Args:
        basepath: A str, pathlib.Path, or otherwise os.PathLike object
            representing the base path where the json file lives.
        docset_id: A str that uniquely identifies the docset the docs
            belong to.

    Returns:
        A pathlib.Path object representing the full path to the 'docs'
        json file.
    """
    return Path(basepath) / f'{docset_id}_docs.json'


def compose_counts_json_filepath(basepath: PathLike, docset_id: str) -> Path:
    """Get the full filepath to a 'counts' json file for a docset.

    Args:
        basepath: A str, pathlib.Path, or otherwise os.PathLike object
            representing the base path where the json file lives.
        docset_id: A str that uniquely identifies the docset the counts
            belong to.

    Returns:
        A pathlib.Path object representing the full path to the
        'counts' json file.
    """
    return Path(basepath) / f'{docset_id}_counts.json'


def _is_file_empty(fpath: PathLike) -> bool:
    """Returns True if a file is empty or does not exist."""
    try:
        fh = open(fpath, 'r')
    except FileNotFoundError:
        return True
    with fh:
        return not bool(fh.readline())


def _get_data(fpath: PathLike) -> Dict[str, Any]:
    """Gets JSON data from a filepath and returns it as a dict."""
    try:
        fh = open(fpath, 'r')
    except FileNotFoundError:
        return {}
    with fh:
        try:
            return ujson.loads(fh.read())
        except ujson.JSONDecodeError:
            return {}


def _update_data(fpath: PathLike, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates JSON data at a filepath with the given user_data (dict).

    The updated JSON is saved and the new data is returned as a dict.
    If a value in `user_data` is None, the existing value for that key
    remains untouched.
    """
    data = _get_data(fpath)
    for key, val in user_data.items():
        if val is not None:
            data[key] = val
    with open(fpath, 'w') as fh:
        fh.write(ujson.dumps(data))
    return data


class FileSet:
    """Class for managing relevant docset files.

    Each docset comprises three JSON files:
        - 'terms' (containing facet terms and search terms).
        - 'docs' (containing all documents in the docset, represented
           as a separate JSON object per line). These tend to be tricky
           because a docset may not fit into memory. They have to be
           streamed to/from disk.
        - 'counts' (containing counts of facet terms that appear in the
          docset).

    Files are saved to a base path (which the DocSet gets from the
    user) using the docset.id in the file name. Users specify the base
    path but otherwise do not have to juggle file names. So, although
    this technically isn't private, users will generally only have to
    deal with it via the DocSet class.

    Attributes:
        basepath: A pathlib.Path object representing the base path
            where the files in the fileset live. (All three files in
            a fileset must have the same base path.)
        docset_id: The unique identifier (str) for the docset the
            fileset belongs to. This is part of the saved file names.
        terms_filepath: A pathlib.Path object pointing to the 'terms'
            file for this fileset.
        docs_filepath: A pathlib.Path object pointing to the 'docs'
            file for this fileset.
        counts_filepath: A pathlib.Path object pointing to the 'counts'
            file for this fileset.
        filepaths: A list of the three file paths (terms, docs, counts).
        terms_file_empty: True if the 'terms' file is empty.
        docs_file_empty: True if the 'docs' file is empty.
        counts_file_empty: True if the 'counts' files is empty.
        search_terms: The list of search terms in the 'terms' file.
        facet_terms: A dict mapping facets to facet terms, from the
            'terms' file.
        docs: A generator that iterates through docs in the 'docs'
            file (as dictionaries).
        total_docs: The number of documents in the 'docs' file.
        facet_value_counts: A dict mapping facets to lists of facet
            value counts (for documents in the 'docs' file).
    """
    def __init__(self, basepath: PathLike, docset_id: str) -> None:
        """Inits a FileSet instance.

        Args:
            basepath: A str, pathlib.Path, or otherwise os.PathLike
                object. See `basepath` attribute.
            docset_id: See `docset_id` attribute.
        """
        self._docset_id = docset_id
        self._basepath = Path(basepath)
        self._terms_fpath = compose_terms_json_filepath(basepath, docset_id)
        self._docs_fpath = compose_docs_json_filepath(basepath, docset_id)
        self._counts_fpath = compose_counts_json_filepath(basepath, docset_id)
        self._search_terms: Optional[List[str]] = None
        self._facet_terms: Optional[Dict[str, List[str]]] = None
        self._total_docs: int = 0
        self._facet_value_counts: Optional[FacetValueCountsReturn] = None

    @property
    def docset_id(self) -> str:
        """The docset.id associated with this fileset.

        See the `docset_id` attribute.
        """
        return self._docset_id

    @property
    def basepath(self) -> Path:
        """The base Path object where this fileset is saved.

        See the `basepath` attribute.
        """
        return self._basepath

    @property
    def terms_filepath(self) -> Path:
        """The Path object for the 'terms' file.

        See the `terms_filepath` attribute.
        """
        return self._terms_fpath

    @property
    def docs_filepath(self) -> Path:
        """The Path object for the 'docs' file.

        See the `docs_filepath` attribute.
        """
        return self._docs_fpath

    @property
    def counts_filepath(self) -> Path:
        """The Path object for the 'counts' file.

        See the `counts_filepath` attribute.
        """
        return self._counts_fpath

    @property
    def filepaths(self) -> List[Path]:
        """List containing the terms, docs, and counts Path objects.

        See the `filepaths` attribute.
        """
        return [self._terms_fpath, self._docs_fpath, self._counts_fpath]

    @property
    def terms_file_empty(self) -> bool:
        """True if the 'terms' file is currently empty.

        See the `terms_file_empty` attribute.
        """
        return _is_file_empty(self._terms_fpath)

    @property
    def docs_file_empty(self) -> bool:
        """True if the 'docs' file is currently empty.

        See the `docs_file_empty` attribute.
        """
        return _is_file_empty(self._docs_fpath)

    @property
    def counts_file_empty(self) -> bool:
        """True if the 'counts' file is currently empty.

        See the `counts_file_empty` attribute.
        """
        return _is_file_empty(self._counts_fpath)

    @property
    def search_terms(self) -> Optional[List[str]]:
        """The list of search terms from 'terms'.

        See the `search_terms` attribute.
        """
        if self._search_terms is None:
            self._refresh_terms()
        return self._search_terms

    @property
    def facet_terms(self) -> Optional[Dict[str, List[str]]]:
        """A dict mapping facet names to facet terms, from 'terms'.

        See the `facet_terms` attribute.
        """
        if self._facet_terms is None:
            self._refresh_terms()
        return self._facet_terms

    @property
    def total_docs(self) -> int:
        """The count of total documents in 'docs'.

        See the `total_docs` attribute.
        """
        if self._total_docs == 0:
            self._refresh_counts()
        return self._total_docs

    @property
    def facet_value_counts(self) -> Optional[FacetValueCountsReturn]:
        """Dict mapping facets to fvalue counts, based on 'docs'.

        The returned dict is structured as follows:
        {
            'First Facet Name': [
                ('most populous facet value', 100),
                ('next most populous facet value', 90),
                ('etc.', 80),
            ],
            'Second Facet Name': [
                ('first facet value', 200),
                ('next facet value', 150),
                ('etc.', 125)
            ]
        }

        See the `facet_value_counts` attribute.
        """
        if self._facet_value_counts is None:
            self._refresh_counts()
        return self._facet_value_counts

    @property
    def docs(self) -> Iterator[Dict[str, Any]]:
        """Document iterator, yields one dict per doc in 'docs.'

        See the `docs` attribute.
        """
        try:
            fh = self._docs_fpath.open('r')
        except FileNotFoundError:
            return iter([])
        with fh:
            for jsonline in fh:
                yield ujson.loads(jsonline)

    def _refresh_terms(self, data: Optional[Mapping[str, Any]] = None) -> None:
        """Refreshes terms from the file or from the provided data."""
        data = data or _get_data(self._terms_fpath)
        self._search_terms = data.get('search_terms')
        self._facet_terms = data.get('facet_terms')

    def _refresh_counts(self,
                        data: Optional[Mapping[str, Any]] = None) -> None:
        """Refreshes counts from the file or from the provided data."""
        data = data or _get_data(self._counts_fpath)
        self._total_docs = data.get('total_docs', 0)
        self._facet_value_counts = data.get('facet_value_counts')

    def save_terms(self,
                   search_terms: Optional[Sequence[str]] = None,
                   facet_terms: Optional[Mapping[str, Sequence[str]]] = None
                   ) -> None:
        """Saves sets of search and/or facet terms to disk.

        If an argument is None, the existing values for that item are
        left alone -- i.e., you can update only one or the other, if
        you wish.

        Args:
            search_terms: (Optional.) A sequence of strings to save as
                search terms for this fileset. If None, the search
                terms in the 'terms' file will remain unchanged. Pass
                an empty sequence to clear search terms in the file.
            facet_terms (Optional.) A mapping of facets to sequences of
                facet terms for each facet. If None, the facet terms in
                the 'terms' file will remain unchanged. Pass an empty
                mapping to clear facet terms in the file.
        """
        data = _update_data(self._terms_fpath, {
            'search_terms': search_terms,
            'facet_terms': facet_terms
        })
        self._refresh_terms(data)

    def save_counts(self,
                    total_docs: Optional[int] = None,
                    facet_value_counts: Optional[FacetValueCountsArg] = None
                    ) -> None:
        """Saves total_docs or facet_value_counts to disk.

        If an argument is None, the existing values for that item are
        left alone -- i.e., you can update only one or the other, if
        you wish.

        Args:
            total_docs: (Optional.) An integer to save as the total
                number of documents in this docset. If None, the
                total_docs value in 'counts' remains unchanged.
            facet_value_counts: (Optional.) A mapping of facet names
                to sequences of (facet value, count) tuples, describing
                the facet value counts for a set of documents. If None,
                the facet_value_counts in 'counts' remains unchanged.
        """
        data = _update_data(self._counts_fpath, {
            'total_docs': total_docs,
            'facet_value_counts': facet_value_counts
        })
        self._refresh_counts(data)

    def stream_docs_to_file(self,
                            docs: Iterable[Dict[str, Any]],
                            overwrite: bool = True
                            ) -> Iterator[Dict[str, Any]]:
        """Create an iterator that saves docs to disk as it iterates.

        Args:
            docs: An iterable containing the documents you wish to save
                to disk. Each doc is a mapping of fields to values,
                suitable for saving as a JSON object.
            overwrite: (Optional.) If True, the existing 'docs' file is
                overwritten at the start of iteration. Otherwise, the
                existing file is appended to. Default is True.

        Returns:
            An iterator that yields each doc in `docs` but saves the
            document to disk (the 'docs' file) before yielding. Saves
            documents one at a time, as you iterate. (If you fail to
            iterate, the documents are not saved.)
        """
        mode = 'w' if overwrite else 'a'
        with self._docs_fpath.open(mode) as fh:
            for doc in docs:
                fh.write(f'{ujson.dumps(doc)}\n')
                yield doc

    def clear(self) -> None:
        """Clears out this FileSet and deletes all three files."""
        # The below try/except block is needed to support Python 3.7.
        # On 3.8+, we can use `fpath.unlink(missing_ok=True)` to
        # try to delete the file while silencing "not found" errors.
        # But this is not available on 3.7. So we have to catch and
        # ignore the error, instead.
        try:
            self._terms_fpath.unlink()
            self._docs_fpath.unlink()
            self._counts_fpath.unlink()
        except FileNotFoundError:
            pass
        self._search_terms = None
        self._facet_terms = None
        self._total_docs = 0
        self._facet_value_counts = None


class SchemaToFileSetLikeAdapter:
    """Class that adapts a BenchmarkSchema instance for DocSet use.

    The data that populates a DocSet instance may come from disk
    (via a FileSet) or it may be generated from a BenchmarkSchema. If
    generated from a BenchmarkSchema, the data may be saved to disk
    (via a FileSet).

    The purpose of this class is to provide an interface on top of a
    BenchmarkSchema instance so that a DocSet can access search terms,
    facet terms, counts, and docs without having to know whether the
    underlying data is coming from disk or being generated dynamically.
    It also allows (optionally) saving to a new FileSet.

    Under normal circumstances you should neither have to instantiate
    nor interact with an instance of this class yourself. The DocSet
    will handle that for you via the `DocSet.from_schema` factory
    method.

    One thing to be aware of is behavior vis-a-vis files. For instance,
    given this docset:

    >>> mypath = Path('/home/myuser/benchmark_files')
    >>> dset = DocSet.from_schema('docset1', myschema, savepath=mypath)

    The first time you iterate through `dset.docs`, it streams the docs
    to a file in your savepath. If that file already exists, it is
    overwritten (the new documents replace the old):

    >>> for doc in dset.docs:
    ...     pass
    >>>

    If you iterate through `dset.docs` again using the same object, it
    will NOT generate new documents -- it will read from disk and yield
    the same document set, behaving exactly like a FileSet instance.

    But at any point you can set the `file_action` attribute to change
    the behavior when a 'docs' file already exists: 'w' will overwrite,
    'a' will append, and anything else (e.g., 'r') will read. Following
    the above example -- if we did want to generate brand new documents
    and overwrite the ones we just generated, we could do this:

    >>> dset.source.file_action = 'w'
    >>> for doc in dset.docs:
    ...     pass
    >>>

    ... or we could just instantiate a new DocSet:

    >>> dset = DocSet.from_schema('docset1', myschema, savepath=mypath)
    >>> for doc in dset.docs:
    ...     pass
    >>>

    Attributes:
        docset_id: The unique identifier (str) for the docset using
            this adapter.
        schema: The BenchmarkSchema instance being adapted.
        fileset: The FileSet instance used to save data to disk for
            this docset. If this is None, then documents are not saved
            to disk when they are generated. If documents are not saved
            to disk, they are not otherwise cached by instances of this
            class.
        search_terms: The list of search terms from the schema.
        facet_terms: A dict mapping facet names to facet terms, from
            `schema.facet_fields`.
        docs: A generator that iteratively creates new documents from
            the schema OR iterates through documents saved to disk,
            depending on the `fileset` and `file_action` attributes.
            - If `fileset` is not set, then it creates new documents
              without saving them to disk.
            - If `fileset` is set and `file_action` is 'w' (write) or
              'a' (append), then new documents are generated and saved
              to disk. 'w' overwrites existing saved documents at the
              start of iteration; 'a' appends to existing saved docs.
            - If `fileset` is set but `file_action` is any other value
              (such as 'r'), then no new docs are created -- instead,
              it iterates through docs already saved to disk.
            When new docs are generated, it stops iteration when it
            reaches the limit configured in `schema.numdocs`.
        total_docs: Tracks the total number of documents generated so
            far as you iterate through `docs`.
        facet_value_counts: A dict mapping facet names to lists of
            facet value counts. Note that this attribute is None until
            the number docs generated (via `docs`) reaches the limit
            configured in schema.numdocs.
        file_action: If a FileSet instance is set via the `fileset`
            attribute, this value determines what happens when a `docs`
            iterator is generated: 'w' (new docs overwrite existing),
            'a' (new docs append to existing), or anything else (docs
            are read from the existing file).
    """
    def __init__(self,
                 docset_id: str,
                 schema: BenchmarkSchema,
                 savepath: Optional[PathLike] = None) -> None:
        """Inits a SchemaToFileSetAdapter instance.

        Args:
            docset_id: See `docset_id` attribute.
            schema: See `schema` attribute. The provided schema MUST be
                configured (via the `schema.configure` method) before
                being passed in here.
            savepath: (Optional.) Base path where generated data should
                be saved to disk. If provided, a new FileSet is
                instantiated using this as the basepath. Facet terms,
                search terms, docs, and facet counts are saved there as
                schema docs are generated. If not provided, schema data
                does not get saved to disk.
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

    def _make_initial_docs_iterator(self) -> Iterator[Dict[str, Any]]:
        """Configures and returns a basic docs iterator."""
        self._total_docs = 0
        self._facet_value_counts: Dict[str, List[Tuple[str, int]]] = {}
        self._facet_value_groups: Dict[str, Dict[str, int]] = {}
        self._schema.reset_fields()
        for _ in range(self._schema.num_docs or 0):
            doc = self._schema()
            self._update_tallies(doc)
            yield doc

    def _update_tallies(self, doc: Mapping[str, Any]) -> None:
        """Updates internal running totals for the given doc."""
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

    def _finalize_facet_counts(self) -> None:
        """Generates final facet value counts from running totals."""
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
    def docset_id(self) -> str:
        """The docset.id of the DocSet using this adapter.

        See the `docset_id` attribute.
        """
        return self._docset_id

    @property
    def fileset(self) -> Optional[FileSet]:
        """The FileSet instance being used to save data.

        See the `fileset` attribute.
        """
        return self._fileset

    @property
    def schema(self) -> BenchmarkSchema:
        """The underlying BenchmarkSchema.

        See the `schema` attribute.
        """
        return self._schema

    @property
    def search_terms(self) -> Optional[List[str]]:
        """The list of search terms from the schema.

        See the `search_terms` attribute.
        """
        return self.schema.search_terms

    @property
    def facet_terms(self) -> Dict[str, List[str]]:
        """Dict mapping facet names to facet terms.

        See the `facet_terms` attribute.
        """
        return self._facet_terms

    @property
    def total_docs(self) -> int:
        """The total number of docs generated so far.

        See the `total_docs` attribute.
        """
        return self._total_docs

    @property
    def facet_value_counts(self) -> Optional[FacetValueCountsReturn]:
        """Dict mapping facet names to facet value counts.

        Note that this only returns anything if all needed docs in the
        docset (i.e. self.schema.numdocs) have been generated. Until
        then facet value counts are unknown, so this returns None.

        See the `facet_value_counts` attribute.
        """
        return self._facet_value_counts

    @property
    def docs(self) -> Iterator[Dict[str, Any]]:
        """A new docs iterator.

        The returned iterator functions differently depending on state:
            - If there is no underlying fileset, the schema is reset
              to generate new documents.
            - If the 'file_action' attr is 'w' or 'a', new documents
              are streamed to disk. ('w' overwrites the existing file,
              while 'a' appends to it.)
            - Otherwise, docs from the existing fileset are read and
              returned.

        See the `docs` attribute.
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
    - Under normal circumstances you should use one of the two factory
      methods to instantiate a new DocSet, depending on the source of
      DocSet data: `from_schema` if you are generating documents from a
      schema object, or `from_disk` if you are loading documents from
      disk.
    - If you are using `from_schema`, you can provide a 'savepath'
      kwarg to save the DocSet to disk for later reuse.
    - Then just iterate through the DocSet.docs property to access your
      documents -- index them into Solr, etc.
    - You can iterate through DocSet.docs multiple times. Just be aware
      that the behavior may change depending on your data source.
      - If you are using a schema to generate new documents and you've
        saved them to disk on the first pass (i.e., using a savepath),
        then you will get those same documents loaded from disk on
        subsequent passes.
      - If you're using a schema *without* a savepath, new documents
        get generated with each new pass.
      - If you've loaded documents from disk, then you get the same
        documents with each pass.

    Attributes:
        source: Data source object for the DocSet. This could be a
            FileSet or a SchemaToFileSetLikeAdapter.
        id: A str used to uniquely identify a document set. E.g., you
            may create different document sets, where each has specific
            qualities useful for benchmarking behavior against a given
            Solr configuration. You must give each of these a unique ID
            to reference it in saved files and reports.
        search_terms: The list of search terms from the data source.
        facet_terms: A dict mapping facet names to lists of facet
            terms, from the data source.
        docs: The `docs` iterator from the data source.
        total_docs: The `total_docs` number from the data source.
        facet_value_counts: A dict mapping facet names to lists of
            (facet value, count) tuples, from the data source.
        fileset: A FileSet where data for this DocSet has been saved
            or will be saved. If `source` is a FileSet, then this is
            the same object as `source`. Otherwise it is from
            `source.fileset`.
    """
    def __init__(self,
                 source: Union[FileSet, SchemaToFileSetLikeAdapter]) -> None:
        """Inits a DocSet instance.

        Instead of using this, see the `from_schema` and `from_disk`
        factory methods. Likely you want to use one of these to
        configure the 'source'.
        """
        self.source = source

    @property
    def id(self) -> str:
        """The str that uniquely identifies your document set.

        See the `id` attribute.
        """
        return self.source.docset_id

    @property
    def search_terms(self) -> Optional[List[str]]:
        """The list of search terms from the data source.

        See the `search_terms` attribute.
        """
        return self.source.search_terms

    @property
    def facet_terms(self) -> Optional[Dict[str, List[str]]]:
        """The facet_terms dict from the data source.

        See the `facet_terms` attribute.
        """
        return self.source.facet_terms

    @property
    def docs(self) -> Iterator[Dict[str, Any]]:
        """The docs iterator from the data source.

        See the `docs` attribute.
        """
        return iter(self.source.docs)

    @property
    def total_docs(self) -> int:
        """The total_docs number from the data source.

        See the `total_docs` attribute.
        """
        return self.source.total_docs

    @property
    def facet_value_counts(self) -> Optional[FacetValueCountsReturn]:
        """The facet_value_counts dict from the data source.

        See the `facet_value_counts` attribute.
        """
        return self.source.facet_value_counts

    @property
    def fileset(self) -> Optional[FileSet]:
        """The FileSet where data for this DocSet is saved.

        See the `fileset` attribute.
        """
        try:
            # Is the source itself a FileSet-like object?
            self.source.basepath  # type: ignore[union-attr]
        except AttributeError:
            return self.source.fileset  # type: ignore[union-attr]
        return self.source  # type: ignore[return-value]

    @classmethod
    def from_schema(cls: Type[D],
                    docset_id: str,
                    schema: BenchmarkSchema,
                    savepath: Optional[PathLike] = None) -> D:
        """Creates a new DocSet instance from a BenchmarkSchema.

        This is a class factory method for instantiating DocSets. Use
        this (or `from_disk`) instead of instantiating them directly.

        Args:
            docset_id: The unique ID str for the new DocSet instance.
            schema: The BenchmarkSchema instance to use.
            savepath: (Optional.) A pathlib.Path-like or str pointing
                to the disk location where you want to save the files
                generated when creating documents in this DocSet. If
                this is not provided, then documents are not saved to
                disk. (Iterating through `docs` multiple times will
                generate multiple sets of documents.)
        """
        source = SchemaToFileSetLikeAdapter(docset_id, schema, savepath)
        return cls(source)

    @classmethod
    def from_disk(cls: Type[D], docset_id: str, loadpath: PathLike) -> D:
        """Creates a new DocSet instance from saved data via a FileSet.

        This is a class factory method for instantiating DocSets. Use
        this (or `from_schema`) instead of instantiating them directly.

        Args:
            docset_id: The unique ID str for the new DocSet instance.
            loadpath: A pathlib.Path-like or str pointing to the disk
                location containing the saved files you want to load.
        """
        fileset = FileSet(loadpath, docset_id)
        if fileset.terms_file_empty or fileset.docs_file_empty:
            raise FileNotFoundError(
                f'DocSet source files are empty or missing. Expected to find '
                f'"{fileset.terms_filepath}" and "{fileset.docs_filepath}". '
                f'Please check "{fileset.basepath}" and try again.'
            )
        return cls(fileset)
