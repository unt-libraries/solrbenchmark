"""
Make sets of documents for Solr benchmarking.
"""

from datetime import datetime

import ujson

from utils import helpers, solr
from utils.test_helpers import solr_factories as sf

from . import terms


def make_docs(total_docs, search_terms, st_weights, facet_terms, profile_params,
              sf_params, ff_params, report_every=1000):
    """
    Make `total_docs` documents using the given terms and parameters.

    Provide a list of `search_terms`, search term weights
    (`st_weights`), and `facet_terms`. Also provide `profile_params` (a
    `parameters.ProfileParams` object), `sf_params` (a
    `parameters.SearchFieldParams` object), and `ff_params` (a
    `parameters.FacetFieldParams` object).

    This will create a `solr_factories.SolrProfile` object, appropriate
    gen overrides, and a `solr_factories.SolrFixtureFactory` object.
    The gen overrides handle: 1) injecting your search_terms into the
    correct search fields (based on `sf_params`) to create the
    specified distribution based on `st_weights`, and 2) using
    `facet_terms` to populate the correct facet fields based on
    `ff_params`.

    The `SolrFixtureFactory` object makes and returns a list of dicts
    representing docs for loading into Solr. (Note that you may still
    need to do some data conversion to serialize the data, such as
    converting datetimes to strings.)

    This process generates docs at the rate of about 1000 every 10-20
    seconds, depending on several factors (your hardware, amount of
    data you're generating, etc.). Generating several thousand for a
    good benchmark can take several minutes. You can use `report_every`
    to track progress, printing a notification to stdout every so many
    records. Default is 1000. Silence notifications entirely using 0 or
    None.
    """
    def _make_kwargs(params, base_st_chance_per_sf=None):
        kwargs = {}
        if 'min_per_rec' in params:
            kwargs['mn'] = params.min_per_rec
        if 'max_per_rec' in params:
            kwargs['mx'] = params.max_per_rec
        if 'avg_per_rec' in params:
            kwargs['mu'] = params.avg_per_rec
        occ_factor = params.get('occ_factor', 1.0)
        kwargs['chance_of_0'] = (1.0 - occ_factor) * 100
        if base_st_chance_per_sf is not None:
            chance = base_st_chance_per_sf / occ_factor
            kwargs['chance_of_injection'] = chance if chance < 100 else 100
        return kwargs

    profile_kwargs = {k: v for k, v in profile_params.items() if k != 'name'}
    profile = sf.SolrProfile(profile_params.name, **profile_kwargs)
    factory = sf.SolrFixtureFactory(profile)

    gen_overrides = {}
    base_st_chance_per_sf = 50 / len(sf_params)
    for sfield, params in sf_params.items():
        kwargs = _make_kwargs(params, base_st_chance_per_sf)
        gen_overrides[sfield] = profile.gen_factory(
            terms.make_terms_injector_gen(
                search_terms, st_weights, params.gen, **kwargs
            )
        )
    for ffield, params in ff_params.items():
        fterms = facet_terms[ffield]
        nterms = len(fterms)
        mu = helpers.clamp(nterms * 0.01, minnum=1.0)
        sigma = helpers.clamp(nterms * 0.1, minnum=1.0, maxnum=500.0)
        weights = helpers.distribute(len(fterms), helpers.gauss_cdr,
                                     mu=mu, sigma=sigma)
        kwargs = _make_kwargs(params)
        gen_overrides[ffield] = profile.gen_factory(
            terms.make_terms_gen(fterms, weights, **kwargs)
        )
    return factory.make(total_docs, **gen_overrides, _report_every=report_every)


class BenchmarkTestDocSet(object):
    """
    Create and manage terms and documents for running benchmark tests.

    This provides a convenient way to encapsulate the test data you'll
    need for reproducible benchmark tests: lists of test documents
    along with the lists of search terms and facets used to create
    them, plus counts of facet values that occur in the test doc set.

    Generally you won't need to use `__init__` to instantiate docset
    objects. To generate a test docset from scratch, you should use the
    `generate` class method. This will create your data and return a
    BenchmarkTestDocSet object. Then you can use `save_to_json_file` to
    serialize the data and save it to disk. For subsequent testing, you
    can use the `load_from_json_file` class method to load your saved
    data into a new BenchmarkTestDocSet instance.

    After generating your data, values should be cast to simple types
    so that you can output to JSON or send to Solr without worrying
    about conversion issues. If you need to specify your own value
    conversions, be sure to create a subclass and override the
    `prep_value_to_serialize` class method.
    """
    def __init__(self, search_terms, facet_terms, docs):
        self.search_terms = search_terms
        self.facet_terms = facet_terms
        self.docs = docs
        self.total_searches = len(search_terms['all'])
        self.total_docs = len(docs)
        self.generate_facet_counts()

    def generate_facet_counts(self):
        self.facet_counts = {}
        self.facet_counts_with_vals = {}
        for ff in self.facet_terms.keys():
            val_groups = {}
            for rec in self.docs:
                for val in rec.get(ff) or []:
                    val_groups[val] = val_groups.get(val, 0) + 1
            counts = sorted(list(val_groups.items()), key=lambda x: x[1],
                            reverse=True)
            self.facet_counts_with_vals[ff] = counts
            self.facet_counts[ff] = [i[1] for i in counts]

    @classmethod
    def generate(cls, profile_params, searchf_params, facetf_params,
                 total_searches, total_docs, verbose=True):
        """
        Generate a new docset object (terms and docs) from scratch.
        
        Uses the given `profile_params` (a `parameters.ProfileParams`
        object), `searchf_params` (a `parameters.SearchFieldParams`
        object), and `facetf_params` (a `parameters.FacetFieldParams`
        object), plus `total_searches` (int) and `total_docs` (int) to
        generate search terms, facet terms, and test documents.

        Returns a new BenchmarkTestDocSet instance.
        """
        report_every = None
        if verbose:
            if total_docs >= 2000:
                report_every = 1000 
            print('Generating search terms.')

        search_terms = terms.make_search_terms(total_searches)
        st_weights = cls.make_search_term_weights(len(search_terms['all']))
        if verbose:
            print('Generating facet terms.')
        facet_terms = terms.make_facet_terms(total_docs, facetf_params)
        if verbose:
            print('Generating docs. (May take several minutes!)')
        docs = make_docs(total_docs, search_terms['all'], st_weights,
                         facet_terms, profile_params, searchf_params,
                         facetf_params, report_every=report_every)
        if verbose:
            print('Preparing docs for serialization (e.g. to Solr, JSON).')
        docs = cls.prep_docs_to_serialize(docs)
        return cls(search_terms, facet_terms, docs)

    @classmethod
    def make_search_term_weights(cls, nterms):
        """
        Get a list of weights for the given number of terms (`nterms`).

        This is used to generate the search term distribution for a doc
        set created via `generate`. Override in a subclass if you want
        a different distribution.
        """
        distribution = helpers.gauss_cdr
        mu = nterms / 2
        sigma = nterms / 2.5
        return helpers.distribute(nterms, distribution, mu=mu, sigma=sigma)

    @classmethod
    def prep_docs_to_serialize(cls, docs):
        """
        Convert values in `docs` to simple types, for serialization.
        """
        formatted = []
        for rec in docs:
            new_rec = {}
            for f, vals in rec.items():
                if isinstance(vals, (list, tuple)):
                    new_rec[f] = [cls.prep_value_to_serialize(v) for v in vals]
                else:
                    new_rec[f] = cls.prep_value_to_serialize(vals)
            formatted.append(new_rec)
        return formatted

    @classmethod
    def prep_value_to_serialize(cls, value):
        """
        Convert an atomic value from a set of docs for serialization.

        If your data has complex types besides `datetime`, override
        this in a subclass to define how to do those conversions. The
        result should be JSON serializable.
        """
        if isinstance(value, datetime):
            return solr.format_datetime_for_solr(value)
        return value

    @classmethod
    def load_from_json_file(cls, filepath):
        """
        Load data from a JSON file and generate a new docset instance.
        """
        with open(filepath) as f:
            json_str = f.read()
        data = ujson.loads(json_str)
        return cls(data['search_terms'], data['facet_terms'], data['docs'])

    def save_to_json_file(self, filepath):
        """
        Serialize this object to JSON and then save to a `filepath`.
        """
        testbed_dict = {
            'search_terms': self.search_terms,
            'facet_terms': self.facet_terms,
            'docs': self.docs
        }
        json_str = ujson.dumps(testbed_dict)
        with open(filepath, 'w') as f:
            f.write(json_str)

