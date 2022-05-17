"""Make sets of documents for Solr benchmarking."""
from pathlib import Path

import ujson


class FileSet:
    """Class for managing relevant docset files."""
    def __init__(self, basepath, fileset_id):
        self._terms_fpath = Path(basepath) / f'{fileset_id}_terms.json'
        self._docs_fpath = Path(basepath) / f'{fileset_id}_docs.json'
        self._search_terms = None
        self._facet_terms = None

    @property
    def terms_filepath(self):
        return self._terms_fpath

    @property
    def docs_filepath(self):
        return self._docs_fpath

    @property
    def search_terms(self):
        if self._search_terms is None:
            data = self._get_terms()
            self._search_terms = data.get('search_terms')
            self._facet_terms = data.get('facet_terms')
        return self._search_terms

    @property
    def facet_terms(self):
        if self._facet_terms is None:
            data = self._get_terms()
            self._search_terms = data.get('search_terms')
            self._facet_terms = data.get('facet_terms')
        return self._facet_terms

    @property
    def docs(self):
        try:
            fh = self._docs_fpath.open('r')
        except FileNotFoundError:
            return iter([])
        with fh:
            for jsonline in fh:
                yield ujson.loads(jsonline)

    def _get_terms(self):
        try:
            fh = self._terms_fpath.open('r')
        except FileNotFoundError:
            return {}
        with fh:
            try:
                return ujson.loads(fh.read())
            except ujson.JSONDecodeError:
                return {}

    def save_terms(self, search_terms=None, facet_terms=None):
        data = self._get_terms()
        if search_terms is not None:
            data['search_terms'] = search_terms
            self._search_terms = search_terms
        if facet_terms is not None:
            data['facet_terms'] = facet_terms
            self._facet_terms = facet_terms
        with self._terms_fpath.open('w') as fh:
            fh.write(ujson.dumps(data))

    def stream_docs_to_file(self, docs, overwrite=True):
        mode = 'w' if overwrite else 'a'
        with self._docs_fpath.open(mode) as fh:
            for doc in docs:
                fh.write(f'{ujson.dumps(doc)}\n')
                yield doc

    def clear(self):
        self._terms_fpath.unlink(missing_ok=True)
        self._docs_fpath.unlink(missing_ok=True)
        self._search_terms = None
        self._facet_terms = None


class TestDocSet:
    """Class for managing sets of test documents."""
    def __init__(self, search_terms, facet_terms, docs):
        self.search_terms = search_terms
        self.facet_terms = facet_terms
        self._docs = docs
        self.total_docs = 0
        self.facet_counts = {}
        self.facet_counts_with_vals = {}
        self._facet_val_groups = {}

    @property
    def docs(self):
        for doc in self._docs:
            yield doc
            self._update_tallies(doc)
        self._finalize_tallies()

    def _update_tallies(self, doc):
        self.total_docs += 1
        for fname in self.facet_terms.keys():
            raw = doc.get(fname) or []
            vals = [raw] if not isinstance(raw, (list, tuple)) else raw
            for val in vals:
                fval_group = self._facet_val_groups.get(fname, {})
                fval_group[val] = fval_group.get(val, 0) + 1
                self._facet_val_groups[fname] = fval_group

    def _finalize_tallies(self):
        for fname in self.facet_terms.keys():
            fval_group = self._facet_val_groups.get(fname, {})
            counts = sorted(list(fval_group.items()), key=lambda x: x[1],
                            reverse=True)
            self.facet_counts_with_vals[fname] = counts
            self.facet_counts[fname] = [i[1] for i in counts]

    @classmethod
    def from_schema(cls, schema, fileset=None):
        if schema.num_docs is None:
            raise ValueError(
                "The 'schema' argument must be a BenchmarkSchema object that "
                "has been configured (via the `configure` method). The schema "
                "just passed has not been configured."
            )
        facet_terms = {f.name: f.terms for f in schema.facet_fields.values()}
        docs = (schema() for _ in range(schema.num_docs))
        if fileset is not None:
            docs = fileset.stream_docs_to_file(docs)
            fileset.save_terms(schema.search_terms, facet_terms)
        return cls(schema.search_terms, facet_terms, docs)

    @classmethod
    def from_fileset(cls, fset):
        return cls(fset.search_terms, fset.facet_terms, fset.docs)
