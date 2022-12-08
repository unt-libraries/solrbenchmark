"""Contains schema components for benchmarking."""
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from fauxdoc.emitters.choice import gaussian_choice
from fauxdoc.emitters.fixed import Static
from fauxdoc.group import ObjectMap
from fauxdoc.mathtools import clamp
from fauxdoc.profile import Field, Schema
from fauxdoc.typing import (
    BoolEmitterLike, FieldLike, IntEmitterLike, StrEmitterLike
)
from solrbenchmark.localtypes import ItemsStrEmitterLike, Number
from solrbenchmark import terms


class SearchField(Field):
    """A "search"-type schema field, for benchmarking.

    This is a subclass of fauxdoc.Field that behaves like a Field,
    generating output data using a given fauxdoc.Emitter-type object,
    but allows random injection of known terms into the output.

    The goal is to facilitate search benchmarking tests. If you
    generate completely random data in your document set, then you
    cannot know what terms will generate any search results. To have
    meaningful tests, you likely want to be able to control what terms
    will generate results sets of various sizes -- ideally, you'd have
    a realistic distribution of terms of various lengths leading to a
    realistic range of result set sizes so that the work Solr has to do
    corresponds with real-world circumstances.

    Initialization is identical to fauxdoc.Field; the associated field
    emitter is the one that generates non-term, random data. The
    `configure_injection` method sets the term emitter and injection
    parameters. Like fauxdoc.Field, calling the field object will
    output a value. If injection parameters have been set, then it uses
    those parameters to determine if injection should occur, where to
    inject the value, and what value to inject -- and it returns the
    field emitter value with the term(s) injected. Otherwise, it just
    generates the field value normally, without injection.

    See the BenchmarkSchema class for information about how to use and
    configure SearchFields in that context. Also see the `terms` module
    for tools that are useful for creating your search terms and search
    term emitters, particularly the `make_search_term_emitter` function.

    Attributes:
        name: See fauxdoc.profile.Field.name.
        emitter: See fauxdoc.profile.Field.emitter.
        repeat_emitter: See fauxdoc.profile.Field.repeat_emitter.
        gate_emitter: See fauxdoc.profile.Field.gate_emitter.
        multi_valued: See fauxdoc.profile.Field.multi_valued.
        hide: See fauxdoc.profile.Field.hide.
        rng_seed: See fauxdoc.profile.Field.rng_seed.
        previous: See fauxdoc.profile.Field.previous.
        terms: The full list of terms that the `term_emitter` can emit.
        term_emitter: A fauxdoc.Emitter-like object that emits from a
            finite set of search terms. The list of terms should be
            accessible from an `items` attribute (such as if it uses
            fauxdoc.mixins.ItemsMixin).
        inject_chance: A float between 0.0 and 1.0 representing the
            chance that an emitted value or list of values should have
            a term injected. This controls the density of search terms
            in a document set.
        overwrite_chance: A float between 0.0 and 1.0 representing the
            chance that a generated search term should overwrite the
            target injection value versus being inserted.
    """

    def __init__(self,
                 name: str,
                 emitter: StrEmitterLike,
                 repeat: Optional[IntEmitterLike] = None,
                 gate: Optional[BoolEmitterLike] = None,
                 rng_seed: Any = None) -> None:
        """Inits a SearchField instance.

        Note that, immediately following initialization, a SearchField
        behaves like a normal fauxdoc.Field. Once term emission has
        been configured (by setting `term_emitter`, `inject_chance`,
        and `overwrite_chance`), the field will generate term-injected
        values.

        Args:
            name: See `name` attribute.
            emitter: See `emitter` attribute.
            repeat: (Optional.) See `repeat` attribute.
            gate: (Optional.) See `gate` attribute.
            rng_seed: (Optional.) See `rng_seed` attribute.
        """
        self._weights = {}
        self._chances = {}
        super().__init__(name, emitter, repeat=repeat, gate=gate, hide=False,
                         rng_seed=rng_seed)
        # This runs the term_emitter setter, which calls the
        # _set_configured method and sets the _current_call_method (to
        # super().__call__).
        self.term_emitter = None

    @property
    def terms(self) -> Optional[List[str]]:
        """The full list of terms the term emitter can emit.

        If `term_emitter` is not set, this is None.
        """
        try:
            return self._emitters.get('term').items
        except AttributeError:
            return None

    @property
    def term_emitter(self) -> Optional[ItemsStrEmitterLike]:
        """A fauxdoc.Emitter-like object that emits search terms.

        See the `term_emitter` attribute.
        """
        return self._emitters.get('term')

    @term_emitter.setter
    def term_emitter(self, term_emitter: ItemsStrEmitterLike) -> None:
        """Sets the `term_emitter` property.

        Args:
            term_emitter: The term emitter instance to set. See the
                `term_emitter` attribute.
        """
        self._emitters['term'] = term_emitter
        self._set_configured()

    @property
    def inject_chance(self) -> float:
        """The chance to inject a term into an emitted value.

        See the `inject_chance` attribute.
        """
        return self._chances.get('inject', 0)

    @inject_chance.setter
    def inject_chance(self, chance: float) -> None:
        """Sets the `inject_chance` property.

        Args:
            chance: The chance value to set. See the `inject_chance`
                attribute.
        """
        chance = clamp(chance, mn=0, mx=1.0)
        self._chances['inject'] = chance
        self._weights['inject'] = [chance, 1.0]
        self._set_configured()

    @property
    def overwrite_chance(self) -> float:
        """The chance injection will fully overwrite an emitted value.

        See the `overwrite_chance` attribute.
        """
        return self._chances.get('overwrite', 0)

    @overwrite_chance.setter
    def overwrite_chance(self, chance: float) -> None:
        """Sets the `overwrite_chance` property.

        Args:
            chance: The chance value to set. See the `overwrite_chance`
                attribute.
        """
        chance = clamp(chance, mn=0, mx=1.0)
        self._chances['overwrite'] = chance
        self._weights['overwrite'] = [chance, 1.0]
        self._set_configured()

    def configure_injection(self,
                            term_emitter: ItemsStrEmitterLike,
                            inject_chance: float = 0.1,
                            overwrite_chance: float = 0.5) -> None:
        """Configures injecting search terms into field output.

        This is a convenience method to use for setting `term_emitter`,
        `inject_chance`, and `overwrite_chance` at one time.

        Before these three properties are set, generating field data
        via this instance will never inject search terms. After they
        are set, generating field data via this instance can include
        search terms (based on the provided injection_chance).

        Args:
            term_emitter: See the `term_emitter` attribute.
            inject_chance: See the `inject_chance` attribute.
            overwrite_chance: See the `overwrite_chance` attribute.
        """
        self.term_emitter = term_emitter
        self.inject_chance = inject_chance
        self.overwrite_chance = overwrite_chance
        self.reset()

    def _set_configured(self) -> None:
        """Sets the __call__ method depending on configured properties.

        This is what flips the switch between emitting with injection
        (if injection properties are set) and without injection (if
        injection properties are not set).
        """
        props = [self.term_emitter, self.inject_chance, self.overwrite_chance]
        if all((prop is not None for prop in props)):
            self._current_call_method = self._configured_call
        else:
            self._current_call_method = super().__call__

    def _should_inject(self) -> bool:
        """Returns True if a term should be injected for a given call."""
        if self._emitters.get('term') and self._chances.get('inject', 0):
            if self._weights['inject'][0] == 1.0:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['inject'])[0]
        return False

    def _should_overwrite(self) -> bool:
        """Returns True if a term should overwrite the existing value."""
        if self._chances.get('overwrite', 0):
            if self._weights['overwrite'][0] == 1.0:
                return True
            return self.rng.choices([True, False],
                                    cum_weights=self._weights['overwrite'])[0]
        return False

    def _inject(self, val: Union[str, List[str]]) -> Union[str, List[str]]:
        """Chooses and injects a term into the given string or list.

        If `val` is a list (for a multi-valued field), a non-None value
        is randomly chosen to inject into, and `_inject` is called
        again on that value.
        """
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

    def __call__(self) -> Optional[Union[str, List[Optional[str]]]]:
        """Generates and returns a data value for this field.

        Term injection only happens if the `term_emitter`,
        `inject_chance`, and `overwrite_chance` properties have all
        been set. If not, it returns a field value without injection.
        """
        # The _current_call_method is set via _set_configured, which
        # is called when any of the three relevant properties are set.
        # If all three are set, it uses _configured_call. Otherwise,
        # it uses super().__call__. (A simpler implementation would use
        # an "is_configured" flag and an if/then test here, but this is
        # slightly faster.)
        return self._current_call_method()

    def _configured_call(self) -> Optional[Union[str, List[Optional[str]]]]:
        """Generates a data value, with injection."""
        self._cache = None
        if self._emitters['gate']():
            number = self._emitters['repeat']()
            val_or_vals = self._emitters['emitter'](number)
            if val_or_vals and self._should_inject():
                val_or_vals = self._inject(val_or_vals)
            self._cache = val_or_vals
        return self._cache


def static_cardinality(cardinality: int) -> Callable[[int], int]:
    """Factory for creating a static cardinality function.

    This is intended to be used to generate a function to pass to
    FacetField.__init__ as the `cardinality_function` argument. Use for
    facet fields that you want to have a specific number of possible
    values.

    Args:
        cardinality: The exact number of facet values.

    Returns:
        A cardinality function, which returns the cardinality for a
        facet field as a function of the total number of documents in
        a document set. In this case the cardinality is static.
    """
    def calculate(total_docs: int) -> int:
        return cardinality
    return calculate


def cardinality_factor(factor: Number,
                       floor: int = 10) -> Callable[[int], int]:
    """Factory for creating a multiplier-based cardinality function.

    This is intended to be used to generate a function to pass to
    FacetField.__init__ as the `cardinality_function` argument. Use for
    facet fields that should have a cardinality based on how many total
    documents are generated.

    Args:
        factor: Multiplying this by the total number of documents in a
            document set or collection should produce the cardinality
            for a facet field for that document set. (E.g.: with a
            factor of 0.1, a document set with 10000 documents should
            have 1000 facet values for this facet field.)
        floor: (Optional.) The minimum cardinality. If total_docs *
            factor is less than this number, then this number will be
            used. Default is 10.

    Returns:
        A cardinality function, which returns the cardinality for a
        facet field as a function of the total number of documents in
        a document set. In this case, the cardinality is a factor of
        the total number of documents.
    """
    def calculate(total_docs: int) -> int:
        return round(clamp(total_docs * factor, mn=floor))
    return calculate


class FacetField(Field):
    """A "facet"-type schema field, for benchmarking.

    This is a subclass of fauxdoc.Field intended to be used for schema
    fields that model facets.

    Facets have special considerations compared to other fields. They
    consist of a definite set of terms and occur within a docset with a
    ~normal distribution. Some facets will be high-cardinality (many
    unique facet terms) and others will be low-cardinality. These are
    important qualities to model since they impact Solr performance.

    Because the cardinality of some facets depends on the number of
    documents in a collection (maybe 10000 documents will have 1000
    facet values; 20000 will have 2000 facet values; etc.) -- we cannot
    generate the set of facet values that a FacetField will emit until
    we know how large the document set is.

    Therefore ...
    - When a FacetField is first initialized, the emitter you assign is
      the one that's used to generate new facet terms from scratch. But
      at that point a concrete facet value set has not yet been
      generated, so attempting to emit field values (by calling the
      field instance) will emit None.
    - The `build_facet_values_for_docset` method is what generates that
      facet value set, using your assigned facet term emitter, and then
      initializes a new emitter to use for choosing values from that
      set. The new emitter has the following qualities.
        - It is a terms.TermChoice emitter. This ensures that it emits
          all facet values at least once, to preserve accurate
          cardinality.
        - It otherwise uses weights that should produce a gaussian
          distribution of facet values within the document set.

    Attributes:
        name: See fauxdoc.profile.Field.name.
        emitter: See fauxdoc.profile.Field.emitter.
        repeat_emitter: See fauxdoc.profile.Field.repeat_emitter.
        gate_emitter: See fauxdoc.profile.Field.gate_emitter.
        multi_valued: See fauxdoc.profile.Field.multi_valued.
        hide: See fauxdoc.profile.Field.hide.
        rng_seed: See fauxdoc.profile.Field.rng_seed.
        previous: See fauxdoc.profile.Field.previous.
        terms: The full list of facet terms that the field emitter can
            emit. (This changes each time new facet values are built
            via `build_facet_values_for_docset`.)
        fterm_emitter: A fauxdoc.Emitter-like object that generates
            new facet terms.
        cardinality_function: A callable for determining this facet
            field's cardinality, or the number of unique facet values,
            as a function of the total number of documents in a docset.
            (The callable should take the total number of docs as an
            int and return the cardinality as an int.)
    """

    def __init__(self,
                 name: str,
                 fterm_emitter: StrEmitterLike,
                 repeat: Optional[IntEmitterLike] = None,
                 gate: Optional[BoolEmitterLike] = None,
                 cardinality_function: Optional[Callable[[int], int]] = None,
                 rng_seed: Any = None) -> None:
        """Inits a FacetField instance.

        Immediately following initialization, calling a FacetField only
        returns None. The `build_facet_values_for_docset` method must
        be called to generate facet values to output.

        Args:
            name: See `name` attribute.
            fterm_emitter: See `fterm_emitter_attribute`.
            repeat: (Optional.) See `repeat` attribute.
            gate: (Optional.) See `gate` attribute.
            cardinality_function: (Optional.) See
                `cardinality_function` attribute.
            rng_seed: (Optional.) See `rng_seed` attribute.
        """
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
    def terms(self) -> Optional[List[str]]:
        """The full list of facet terms the field emitter can emit.

        If facet values have not been built, this is None.
        """
        try:
            return self._emitters.get('emitter').value
        except AttributeError:
            return self._emitters.get('emitter').items
        except AttributeError:
            return None

    @property
    def fterm_emitter(self) -> Optional[StrEmitterLike]:
        """The fauxdoc.Emitter-like obj that creates new facet terms.

        See the `fterm_emitter` attribute.
        """
        return self._emitters['fterm']

    @fterm_emitter.setter
    def fterm_emitter(self, emitter: StrEmitterLike) -> None:
        """Sets the `fterm_emitter` property.

        Args:
            emitter: The emitter instance to set. See the
                `fterm_emitter` attribute.
        """
        self._emitters['fterm'] = emitter

    def build_facet_values_for_docset(self, total_docs: int) -> None:
        """Builds or rebuilds facet values for a document set.

        Note that this regenerates facets terms and resets the field
        each time it runs. You only need to run it once per full
        document set.

        Args:
            total_docs: The total number of docs in the docset to
                generate facet values for.
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
    """A schema class for benchmarking.

    Builds on fauxdoc.profile.Schema to provide facilities for search
    fields (SearchField instances) and facet fields (FacetField
    instances). Specifically, the `configure` method configures
    each SearchField and builds facet values for each FacetField.

    See the `terms` module for tools that are useful for creating your
    search terms and search term emitters, particularly the
    `make_search_term_emitter` function.

    Attributes:
        fields: See fauxdoc.profile.Schema.fields.
        hidden_fields: See fauxdoc.profile.Schema.hidden_fields.
        public_fields: See fauxdoc.profile.Schema.public_fields.
        search_fields: A fauxdoc.group.ObjectMap that maps field names
            to field objects, containing all SearchField objects.
        facet_fields: A fauxdoc.group.ObjectMap that maps fields names
            to field objects, containing all FacetField objects.
        search_term_emitter: A fauxdoc.Emitter-like object that emits
            from a finite set of search terms. This is used as the
            `term_emitter` for all SearchField instances on the schema.
            Is None if no `search_term_emitter` is configured.
        search_terms: The full list of terms that `search_term_emitter`
            can emit. Is None if no `search_term_emitter` is
            configured.
        num_docs: The size of the document set this schema instance is
            currently configured for. Is None if this schema instance
            has not yet been configured via the `configure` method.
    """

    def __init__(self, *fields: FieldLike) -> None:
        """Inits a BenchmarkSchema instance.

        After initialization, the `configure` method needs to be used
        to ensure all search and facet fields are properly configured.

        Args:
            fields: See `fields` attribute.
        """
        self.search_fields = ObjectMap({})
        self.facet_fields = ObjectMap({})
        # __init__ uses `add_fields` to add fields to the schema, which
        # ensures fields get added to self.search_fields and
        # self.facet_fields, as appropriate.
        super().__init__(*fields)
        self._search_term_emitter = None
        self._num_docs = None

    @property
    def search_term_emitter(self) -> Optional[ItemsStrEmitterLike]:
        """A fauxdoc.Emitter-like object that emits search terms.

        See `search_term_emitter` attribute.
        """
        return self._search_term_emitter

    @property
    def search_terms(self) -> Optional[List[str]]:
        """The full list of terms that `search_term_emitter` can emit.

        See `search_terms` attribute.
        """
        try:
            return self._search_term_emitter.items
        except AttributeError:
            return None

    @property
    def num_docs(self) -> Optional[int]:
        """The size of the docset this is currently configured for.

        See `num_docs` attribute.
        """
        return self._num_docs

    @num_docs.setter
    def num_docs(self, num_docs: int) -> None:
        """Sets the `num_docs` property.

        Note: facet values for each facet field are rebuilt when this
        is set.

        Args:
            num_docs: See `num_docs` attribute.
        """
        self._num_docs = num_docs
        self.facet_fields.do_method('build_facet_values_for_docset', num_docs)

    def add_fields(self, *fields: FieldLike) -> None:
        """Adds fields to your schema, in the order provided.

        Args:
            fields: See `fields` attribute.
        """
        super().add_fields(*fields)
        for field in fields:
            if hasattr(field, 'configure_injection'):
                self.search_fields.update({field.name: field})
            if hasattr(field, 'build_facet_values_for_docset'):
                self.facet_fields.update({field.name: field})

    def _get_inj_chance_per_field(self,
                                  td_ratio: Number,
                                  max_per_field: Mapping[str, Number]
                                  ) -> Dict[str, float]:
        """Calculates adjusted injection chances per field.

        Adjusted chances are based on the user-provided term:doc ratio
        and the max ratio that each search field supports. The goal is
        to try to ensure the output as a whole reflects the desired
        term:doc ratio.
        """
        try:
            target = td_ratio / len(max_per_field)
        except ZeroDivisionError:
            return {}
        up_to_t = {}
        above_t = {}
        for fname, max_ in max_per_field.items():
            if max_ <= target:
                up_to_t[fname] = max_
            else:
                above_t[fname] = max_
        if up_to_t:
            ret = {fname: 1.0 for fname in up_to_t.keys()}
            if above_t:
                new_ratio = td_ratio - sum(up_to_t.values())
                ret.update(self._get_inj_chance_per_field(new_ratio, above_t))
            return ret
        return {fname: target / max_ for fname, max_ in max_per_field.items()}

    def configure(self,
                  num_docs: int,
                  search_term_emitter: ItemsStrEmitterLike,
                  term_doc_ratio: float = 0.5,
                  overwrite_chance: float = 0.5,
                  rng_seed: Any = None) -> None:
        """Configures facet and search fields for output.

        If this is not run before outputting schema values, associated
        facet fields will not output values and search fields will not
        inject terms.

        Args:
            num_docs: See `num_docs` attribute.
            search_term_emitter: See `search_term_emitter` attribute.
            term_doc_ratio: (Optional.) The overall desired ratio of
                search terms to docs, designed to help control the base
                number of docs that have search terms and, ultimately,
                how many results you get during search tests. Default
                is 0.5.
                - A target ratio of 1.0 means each document in your
                  docset should have one search term. 0.5 means 50%
                  of documents should have a search term. 5.0 means
                  each document should have 5 search terms.
                - You cannot inject more search terms than there are
                  opportunities to inject search terms, so there is a
                  max possible ratio for each schema, which is: the sum
                  of probabilities that a field will not be None for
                  each search field. I.e., with 5 search fields that
                  always output values, the max ratio is 5.0 (1.0 * 5).
                  With 5 search fields that each may be None 3/4 of the
                  time, the max ratio is 1.25 (0.25 * 5).
                - Actual numbers of results will vary simply due to
                  randomness.
            overwrite_chance: (Optional.) A float between 0.0 and 1.0
                representing the chance that search terms injected into
                search field data will overwrite the original value
                (instead of being inserted). Default is 0.5.
            rng_seed: (Optional.) A valid value for passing to
                random.seed. Used to seed fields before generating
                values (i.e., facet values).
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
