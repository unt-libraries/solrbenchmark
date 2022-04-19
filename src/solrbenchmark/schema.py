"""Contains solrfixture schema components for benchmarking."""
import sys

from solrfixtures.emitters.choice import chance as chance_em, gaussian_choice
from solrfixtures.mathtools import clamp
from solrfixtures.profile import Field, Schema

from solrbenchmark import terms


class SearchField(Field):
    """Implements a search-type field, for benchmarking."""

    def __init__(self, name, emitter, repeat=None, emit_pchance=None,
                 rng_seed=None):
        """Inits a SearchField instance."""
        self._weights = {}
        self._pchances = {}
        if emit_pchance is None:
            self.emit_pchance = 100
            gate = None
        else:
            self.emit_pchance = emit_pchance
            gate = chance_em(self.emit_pchance)
        super().__init__(name, emitter, repeat, gate, rng_seed)
        self.term_emitter = None

    @property
    def term_emitter(self):
        return self._emitters.get('term')

    @term_emitter.setter
    def term_emitter(self, term_emitter):
        self._emitters['term'] = term_emitter

    @property
    def emit_pchance(self):
        return self._pchances.get('emit', 100)

    @emit_pchance.setter
    def emit_pchance(self, pchance):
        self._pchances['emit'] = clamp(pchance, mn=0, mx=100)
        self._update_inject_weights()

    @property
    def inject_pchance(self):
        return self._pchances.get('inject', 0)

    @inject_pchance.setter
    def inject_pchance(self, pchance):
        self._pchances['inject'] = clamp(pchance, mn=0, mx=100)
        self._update_inject_weights()

    def _update_inject_weights(self):
        field_occurrence_factor = 1 / (self.emit_pchance / 100)
        pchance = self.inject_pchance * field_occurrence_factor
        self._weights['inject'] = [clamp(pchance, mn=0, mx=100), 100]

    @property
    def overwrite_pchance(self):
        return self._pchances.get('overwrite', 0)

    @overwrite_pchance.setter
    def overwrite_pchance(self, pchance):
        pchance = clamp(pchance, mn=0, mx=100)
        self._pchances['overwrite'] = pchance
        self._weights['overwrite'] = [pchance, 100]

    def configure_injection(self, term_emitter, inject_pchance=10,
                            overwrite_pchance=50):
        """Configures injecting search terms into field output."""
        self.term_emitter = term_emitter
        self.inject_pchance = inject_pchance
        self.overwrite_pchance = overwrite_pchance
        self.reset()

    def _should_inject(self):
        if self._emitters.get('term') and self._pchances.get('inject', 0):
            if self._weights['inject'][0] == 100:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['inject'])[0]
        return False

    def _should_overwrite(self):
        if self._pchances.get('overwrite', 0):
            if self._weights['overwrite'][0] == 100:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['overwrite'])[0]
        return False

    def _inject(self, new_term, old_term):
        pos = self.rng.choice(range(len(old_term) - 1))
        return ' '.join([old_term[:pos], new_term, old_term[pos:]]).strip()

    def __call__(self):
        """Generates one field value via the emitter."""
        if self._emitters['gate']():
            number = self._emitters['repeat']()
            if self._should_inject():
                should_overwrite = self._should_overwrite()
                term = self._emitters['term']()
                if number is None:
                    if should_overwrite:
                        self._cache = self._emitters['term']()
                    else:
                        self._cache = self._inject(
                            term, self._emitters['emitter']()
                        )
                else:
                    vals = self._emitters['emitter'](number)
                    imax = len(vals) - 1
                    pos = self.rng.choice(range(imax)) if imax else 0
                    if should_overwrite:
                        vals[pos] = term
                    else:
                        vals[pos] = self._inject(term, vals[pos])
                    self._cache = vals
            else:
                self._cache = self._emitters['emitter'](number)
        else:
            self._cache = None
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

    def __init__(self, name, fterm_emitter, repeat=None, emit_pchance=None,
                 cardinality_function=None, rng_seed=None):
        """Inits a FacetField instance."""
        if emit_pchance is None:
            self.emit_pchance = 100
            gate = None
        else:
            self.emit_pchance = emit_pchance
            gate = chance_em(emit_pchance)
        super().__init__(name, None, repeat, gate, rng_seed)
        self.fterm_emitter = fterm_emitter
        if cardinality_function is None:
            self.cardinality_function = static_cardinality(10)
        else:
            self.cardinality_function = cardinality_function

    @property
    def emit_pchance(self):
        return self._emit_pchance

    @emit_pchance.setter
    def emit_pchance(self, pchance):
        self._emit_pchance = clamp(pchance, mn=0, mx=100)

    @property
    def fterm_emitter(self):
        return self._emitters['fterm']

    @fterm_emitter.setter
    def fterm_emitter(self, emitter):
        self._emitters['fterm'] = emitter

    def build_facet_values_for_docset(self, total_docs):
        """Build or rebuild facet values for a document set.

        Note that this regenerates facets terms and resets the field
        each time it runs. You only need to run it once per full
        document set.
        """
        cardinality = self.cardinality_function(total_docs)
        fterms = self.fterm_emitter(cardinality)
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
