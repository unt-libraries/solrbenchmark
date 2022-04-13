"""
Create sets of parameters for benchmark tests.
"""
from collections import UserDict


class ParamsDict(UserDict):
    """
    Utility class for working with dicts of parameters.

    This is a base class. To use, you must create a subclass that has a
    `param_names` attr, used to validate instances -- i.e., keys must
    be in `param_names` or else a KeyError is raised.

    Instantiate as you would any dict, where keys are parameter names
    and values are parameter values. Assuming it validates, key/value
    pairs will be identical to what was supplied. Additionally, all
    possible params are added to the instance as attributes, defaulting
    to None if not provided.

    Example:

    class MyParams(ParamsDict):
        param_names = ('foo', 'bar', 'baz')

    >>> p = MyParams({'foo': 1, 'unknown': 'one'})
    KeyError: "'unknown' not a valid parameter for 'MyParams' class."
    >>> p = MyParams({'foo': 1})
    >>> p
    {'foo': 1}
    >>> p.foo
    1
    >>> p['foo']
    1
    >>> p.get('foo')
    1
    >>> p.bar
    >>> p['bar']
    KeyError: 'bar'
    >>> p.get('bar')
    >>> p.unknown
    AttributeError: 'MyParams' object has no attribute 'unknown'
    """
    param_names = ()

    def __init__(self, params):
        for arg in dict(params).keys():
            if arg not in self.param_names:
                msg = ("'{}' not a valid parameter for '{}' class."
                       "".format(arg, type(self).__name__))
                raise KeyError(msg)
        super().__init__(params)
        all_params = {k: None for k in self.param_names}
        all_params.update(params)
        self.__dict__.update(all_params)


class FieldParamsDict(UserDict):
    """
    Utility for working with dicts of per-field parameters.

    This is a base class. To use, you must create a subclass that has a
    `param_names` attr, used to validate instances.
 
    Instantiate using a nested dict. Keys in the outer dict are field
    names, and values are dicts. Keys in the inner dicts are parameter
    names, and values are parameter values. (Each inner dict is
    converted to a `ParamsDict` instance.)
    """
    param_names = ()

    def __init__(self, params):
        inner_params_type = type('InnerParams', (ParamsDict,),
                                 {'param_names': self.param_names})
        new_d = dict()
        for field, field_params in dict(params).items():
            new_d[field] = inner_params_type(field_params)
        super().__init__(new_d)
        self.__dict__.update(new_d)


class SearchFieldParams(FieldParamsDict):
    """
    Represent sets of parameters for search fields.

    Instantiate using a nested dict. Outer dict keys are names of
    search fields in your schema. Inner dicts must comprise the
    following:

    `gen` -- The 'gen' (generator) function used to generate data or
    terms for a given search field.

    `occ_factor` -- "Occurrence factor," a value between 0 and 1 that,
    when multiplied by the total number of documents in a doc set,
    defines how many of those documents have a value in a given search
    field. 1 means every document has that field populated.

    `min_per_rec`, `max_per_rec`, `avg_per_rec` -- For multi-valued
    search fields, these parameters control the per-field min, max, and
    average number of values that occur.
    """
    param_names = (
        'gen', 'occ_factor', 'min_per_rec', 'max_per_rec', 'avg_per_rec'
    )


class FacetFieldParams(FieldParamsDict):
    """
    Represent sets of parameters for facet fields.

    Instantiate using a nested dict. Outer dict keys are names of
    search fields in your schema. Inner dicts must comprise the
    following:

    `gen` -- The 'gen' (generator) function used to generate terms for
    a given facet field.

    `occ_factor` -- "Occurrence factor," a value between 0 and 1 that,
    when multiplied by the total number of documents in a doc set,
    defines how many of those documents have a value in a given facet
    field. 1 means every document has that field populated.

    `min_per_rec`, `max_per_rec`, `avg_per_rec` -- For multi-valued
    facet fields, these parameters control the per-field min, max, and
    average number of values that occur.

    `cardinality` -- Provide this to define an exact number of unique
    facet terms for this field. If you provide this, do not provide
    `card_factor` or `card_floor`.

    `card_factor` -- "Cardinality factor," a value between 0 and 1
    that defines the number of unique terms for a facet as a portion of
    the total times the field occurs in a document set. If
    `card_factor` is provided instead of `cardinality`, the cardinality
    is calculated as (total_documents * occ_factor * card_factor).

    `card_floor` -- "Cardinality floor," the absolute lowest value you
    want to be used when calculating cardinality for a given field. If
    the `card_factor` calculation is lower than this number, this
    number is used instead.
    """
    param_names = (
        'gen', 'occ_factor', 'min_per_rec', 'max_per_rec', 'avg_per_rec',
        'cardinality', 'card_factor', 'card_floor'
    )


class ProfileParams(ParamsDict):
    """
    Represent SolrProfile parameters.

    Instantiate using a dict of parameters. See the `__init__` method
    of `utils.test_helpers.solr_factories.SolrProfile` for a
    description of each parameter.
    """
    param_names = (
        'name', 'conn', 'schema', 'user_fields', 'unique_fields', 'solr_types',
        'gen_factory', 'default_field_gens'
    )

