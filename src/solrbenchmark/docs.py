"""Make sets of documents for Solr benchmarking."""
import os

import ujson


class FileSet:
    """Class for managing relevant docset files."""
    def __init__(self, basepath, fileset_id):
        self._terms_fpath = os.path.join(basepath, f'{fileset_id}_terms.json')
        self._docs_fpath = os.path.join(basepath, f'{fileset_id}_docs.json')
        self._search_terms = None
        self._facet_terms = None

    @property
    def search_terms(self):
        if self._search_terms is None:
            data = self.get_terms()
            self._search_terms = data.get('search_terms')
            self._facet_terms = data.get('facet_terms')
        return self._search_terms

    @property
    def facet_terms(self):
        if self._facet_terms is None:
            data = self.get_terms()
            self._search_terms = data.get('search_terms')
            self._facet_terms = data.get('facet_terms')
        return self._facet_terms

    def open_terms_file(self, mode='r'):
        return open(self._terms_fpath, mode)

    def open_docs_file(self, mode='r'):
        return open(self._docs_fpath, mode)

    def get_terms(self):
        try:
            fh = self.open_terms_file('r')
        except FileNotFoundError:
            return {}
        with fh:
            try:
                return ujson.loads(fh.read())
            except ujson.JSONDecodeError:
                return {}

    def save_terms(self, search_terms=None, facet_terms=None):
        data = self.get_terms()
        if search_terms is not None:
            data['search_terms'] = search_terms
            self._search_terms = search_terms
        if facet_terms is not None:
            data['facet_terms'] = facet_terms
            self._facet_terms = facet_terms
        with self.open_terms_file('w') as fh:
            fh.write(ujson.dumps(data))

    def stream_docs_to_file(self, docs_gen):
        with self.open_docs_file('w') as fh:
            for doc in docs_gen:
                fh.write(f'{ujson.dumps(doc)}\n')
                yield doc

    def get_docs_gen(self):
        try:
            fh = self.open_docs_file('r')
        except FileNotFoundError:
            return iter([])
        with fh:
            for jsonline in fh:
                yield ujson.loads(jsonline)

    def clear(self):
        try:
            os.remove(self._terms_fpath)
            os.remove(self._docs_fpath)
        except FileNotFoundError:
            pass


class TestDocSet:
    """Class for managing sets of test documents."""
    def __init__(self, search_terms, facet_terms, docs_generator):
        self.search_terms = search_terms
        self.facet_terms = facet_terms
        self._docs = docs_generator
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
            for val in doc.get(fname) or []:
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
    def from_schema(cls, schema, total_docs, fileset=None):
        facet_terms = {f.name: f.terms for f in schema.facet_fields.values()}
        docs_gen = (schema() for _ in range(total_docs))
        if fileset is not None:
            docs_gen = fileset.stream_docs_to_file(docs_gen)
            fileset.save_terms(schema.search_terms, facet_terms)
        return cls(schema.search_terms, facet_terms, docs_gen)

    @classmethod
    def from_fileset(cls, fset):
        return cls(fset.search_terms, fset.facet_terms, fset.get_docs_gen())
