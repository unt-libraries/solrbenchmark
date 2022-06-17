"""Contains solrfixture schema components for benchmarking."""
import sys

from solrfixtures.emitters.choice import chance as chance_em, gaussian_choice
from solrfixtures.emitters.fixed import Static
from solrfixtures.group import ObjectMap
from solrfixtures.mathtools import clamp
from solrfixtures.profile import Field, Schema

from solrbenchmark import terms


class SearchField(Field):
    """Implements a search-type field, for benchmarking."""

    def __init__(self, name, emitter, repeat=None, gate=None, rng_seed=None):
        """Inits a SearchField instance."""
        self._weights = {}
        self._chances = {}
        super().__init__(name, emitter, repeat=repeat, gate=gate, hide=False,
                         rng_seed=rng_seed)
        self.term_emitter = None

    @property
    def terms(self):
        try:
            return self._emitters.get('term').items
        except AttributeError:
            return None

    @property
    def term_emitter(self):
        return self._emitters.get('term')

    @term_emitter.setter
    def term_emitter(self, term_emitter):
        self._emitters['term'] = term_emitter
        self._set_configured()

    @property
    def inject_chance(self):
        return self._chances.get('inject', 0)

    @inject_chance.setter
    def inject_chance(self, chance):
        chance = clamp(chance, mn=0, mx=1.0)
        self._chances['inject'] = chance
        self._weights['inject'] = [chance, 1.0]
        self._set_configured()

    @property
    def overwrite_chance(self):
        return self._chances.get('overwrite', 0)

    @overwrite_chance.setter
    def overwrite_chance(self, chance):
        chance = clamp(chance, mn=0, mx=1.0)
        self._chances['overwrite'] = chance
        self._weights['overwrite'] = [chance, 1.0]
        self._set_configured()

    def configure_injection(self, term_emitter, inject_chance=0.1,
                            overwrite_chance=0.5):
        """Configures injecting search terms into field output."""
        self.term_emitter = term_emitter
        self.inject_chance = inject_chance
        self.overwrite_chance = overwrite_chance
        self.reset()

    def _set_configured(self):
        props = [self.term_emitter, self.inject_chance, self.overwrite_chance]
        if all((prop is not None for prop in props)):
            self._current_call_method = self._configured_call
        else:
            self._current_call_method = super().__call__

    def _should_inject(self):
        if self._emitters.get('term') and self._chances.get('inject', 0):
            if self._weights['inject'][0] == 1.0:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['inject'])[0]
        return False

    def _should_overwrite(self):
        if self._chances.get('overwrite', 0):
            if self._weights['overwrite'][0] == 1.0:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['overwrite'])[0]
        return False

    def _inject(self, val):
        if isinstance(val, list):
            i_opts = [i for i, v in enumerate(val) if v not in (None, [])]
            if i_opts:
                pos = self.rng.choice(i_opts)
                val = list(val)
                val[pos] = self._inject(val[pos])
            return val

        term = self._emitters['term']()
        if self._should_overwrite():
            return term
        pos_max = len(val)
        pos = pos_max if pos_max <= 1 else self.rng.choice(range(pos_max - 1))
        return ' '.join([val[:pos], term, val[pos:]]).strip()

    def __call__(self):
        return self._current_call_method()

    def _configured_call(self):
        """Generates one field value via the emitter."""
        self._cache = None
        if self._emitters['gate']():
            number = self._emitters['repeat']()
            val_or_vals = self._emitters['emitter'](number)
            if val_or_vals and self._should_inject():
                val_or_vals = self._inject(val_or_vals)
            self._cache = val_or_vals
        return self._cache


def static_cardinality(cardinality):
    """Make a function that gives a static cardinality value."""
    def calculate(total_docs):
        return cardinality
    return calculate


def cardinality_factor(factor, floor=10):
    """Make a function that gives a multiplier-based cardinality value."""
    def calculate(total_docs):
        return round(clamp(total_docs * factor, mn=floor))
    return calculate


class FacetField(Field):
    """Implements a facet-type field, for benchmarking.

    Note: "cardinality" refers to how many unique facet terms exist. It
    is often a function of the total number of documents in a document
    set. The 'cardinality_function' attribute defines how to calculate
    cardinality for a given FacetField.
    """

    def __init__(self, name, fterm_emitter, repeat=None, gate=None,
                 cardinality_function=None, rng_seed=None):
        """Inits a FacetField instance."""
        super().__init__(name, Static(None), repeat=repeat, gate=gate,
                         hide=False, rng_seed=rng_seed)
        self.fterm_emitter = fterm_emitter
        if cardinality_function is None:
            self.cardinality_function = static_cardinality(10)
        else:
            self.cardinality_function = cardinality_function
        try:
            self.fterm_emitter.seed(rng_seed)
        except AttributeError:
            pass

    @property
    def terms(self):
        try:
            return self._emitters.get('emitter').value
        except AttributeError:
            return self._emitters.get('emitter').items
        except AttributeError:
            return None

    @property
    def fterm_emitter(self):
        return self._emitters['fterm']

    @fterm_emitter.setter
    def fterm_emitter(self, emitter):
        self._emitters['fterm'] = emitter

    def build_facet_values_for_docset(self, total_docs):
        """Builds or rebuilds facet values for a document set.

        Note that this regenerates facets terms and resets the field
        each time it runs. You only need to run it once per full
        document set.
        """
        cardinality = self.cardinality_function(total_docs)
        fterms = terms.make_vocabulary(self.fterm_emitter, cardinality,
                                       self.rng_seed)
        # I think we prefer a random sort for facet terms, since
        # occurrence isn't really based on term length.
        fterms = sorted(fterms, key=lambda v: self.fterm_emitter.rng.random())
        num_fterms = len(fterms)
        self.emitter = terms.TermChoice(gaussian_choice(
            fterms,
            mu=clamp(num_fterms * 0.01, mn=1.0),
            sigma=clamp(num_fterms * 0.1, mn=1.0, mx=500.0),
            weight_floor=sys.float_info.min
        ))
        self.reset()


class BenchmarkSchema(Schema):
    """Implements a schema class for benchmarking."""

    def __init__(self, *fields):
        """Inits a BenchmarkSchema instance."""
        self.search_fields = ObjectMap({})
        self.facet_fields = ObjectMap({})
        super().__init__(*fields)
        self._search_term_emitter = None
        self._num_docs = None

    @property
    def search_term_emitter(self):
        return self._search_term_emitter

    @property
    def search_terms(self):
        try:
            return self._search_term_emitter.items
        except AttributeError:
            return None

    @property
    def num_docs(self):
        return self._num_docs

    @num_docs.setter
    def num_docs(self, num_docs):
        self._num_docs = num_docs
        self.facet_fields.do_method('build_facet_values_for_docset', num_docs)

    def add_fields(self, *fields):
        """Adds fields to your schema, in the order provided."""
        super().add_fields(*fields)
        for field in fields:
            if hasattr(field, 'configure_injection'):
                self.search_fields.update({field.name: field})
            if hasattr(field, 'build_facet_values_for_docset'):
                self.facet_fields.update({field.name: field})

    def _get_inj_chance_per_field(self, td_ratio, max_per_field):
        """Calculates adjusted injection chances per field ...

        ... based on the user-provided term:doc ratio and the max ratio
        that each search field supports. The goal is to try to ensure
        the output as a whole reflects the desired term:doc ratio."""
        try:
            target = td_ratio / len(max_per_field)
        except ZeroDivisionError:
            return {}
        up_to_t = {}
        above_t = {}
        for fname, num in max_per_field.items():
            if num <= target:
                up_to_t[fname] = num
            else:
                above_t[fname] = num
        if up_to_t:
            ret = {fn: 1.0 for fn in up_to_t.keys()}
            if above_t:
                new_ratio = td_ratio - sum(up_to_t.values())
                ret.update(self._get_inj_chance_per_field(new_ratio, above_t))
            return ret
        return {fn: target / max_ for fn, max_ in max_per_field.items()}

    def configure(self, num_docs, search_term_emitter, term_doc_ratio=0.5,
                  overwrite_chance=0.5, rng_seed=None):
        """Configures facet and search fields for output.

        You should run this before you output schema values. Otherwise,
        your FacetFields won't output values, and your SearchFields
        won't inject terms.

        NOTE:

        `term_doc_ratio` is the overall desired (approximate) ratio of
        terms to docs, designed to help you control the base number of
        docs that each term appears in. Ultimately this helps tailor
        how many results you'll get for each term during tests. For
        instance, assuming 1000 docs in your docset (`num_docs`) and a
        `search_term_emitter` that outputs 10 terms with equal weights:
            - A ratio of 1.0 should give you ~100 results per term.
              In theory nearly all of the 1000 documents should have a
              term injected.
            - A ratio of 0.5 should give you ~50 results per term.
              Nearly half of the 1000 documents should have a term
              injected.

        In practice, other factors also come into play:
            - Term weights. Actual results will follow term weighting
              you've assigned -- such as a gaussian distribution.
            - Number of fields and field gating (how often the fields
              are empty or not). Each SearchField injects ONE term per
              per document, and it honors the "gate" probability -- if
              a field is gated so that it's populated half the time, it
              can't satisfy a term:doc ratio greater than 0.5. (I.e.,
              even if it always injects a term, only half of documents
              will get a term in that field -- the other half will be
              blank.) Ultimately, the sum of probabilities that a field
              is NOT blank for all SearchFields on the schema
              determines the max term_doc_ratio. Example: with five
              search fields that are never empty, you could have max
              5.0 term_doc_ratio. With five search fields that are non-
              empty 0.1 of the time, max term_doc_ratio would be 0.5.
        """
        self.seed_fields(rng_seed)
        self.num_docs = num_docs
        self._search_term_emitter = search_term_emitter
        search_field_names = self.search_fields.keys()

        # In order to determine the actual chance to inject a search
        # term for each search field, we need to know the chance that
        # there will be an *opportunity* to inject a search term -- so
        # we need to know the chance that each search field will emit
        # a non-empty value. The only reliable way to do this is to
        # sample the schema output. (And we have to output full docs in
        # case there are SearchFields using e.g. CopyFields emitters,
        # which rely on other Fields.) This may take a noticeable
        # amount of time, depending on the size of the schema.

        counts = {}
        max_ratio_per_field = {}
        sample_size = 1000
        for i in range(sample_size):
            doc = self()
            for fname in search_field_names:
                if doc[fname]:
                    counts[fname] = counts.get(fname, 0) + 1
                if i == sample_size - 1:
                    max_ratio = counts.get(fname, 0) / sample_size
                    max_ratio_per_field[fname] = clamp(max_ratio, mn=0.0001)
        ratios_per_field = self._get_inj_chance_per_field(term_doc_ratio,
                                                          max_ratio_per_field)
        for fname in search_field_names:
            self.search_fields.get(fname).configure_injection(
                search_term_emitter, ratios_per_field[fname], overwrite_chance
            )
        self.reset_fields()
