"""Contains tests for `schema` module."""
import pytest
from fauxdoc.emitters.choice import chance, Choice
from fauxdoc.emitters.fixed import Iterative, Sequential, Static
from fauxdoc.emitters.fromfields import CopyFields
from fauxdoc.emitters.text import Text, Word
from fauxdoc.emitters.wrappers import WrapOne
from fauxdoc.profile import Field

from solrbenchmark import schema


# Fixtures & Test Data

LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def num_range(min_, max_):
    return Choice(range(min_, max_))


def word(min_, max_, alphabet):
    return Word(Choice(range(min_, max_)), Choice(alphabet))


def text(min_, max_, word_em):
    return Text(Choice(range(min_, max_)), word_em)


def keyword(text_or_word_em):
    return WrapOne(text_or_word_em, lambda val: val.capitalize())


def id_(min_, max_):
    return Iterative(lambda: (f"b{n}" for n in range(min_, max_)))


def num_range_string(min_, max_):
    return Choice([str(num) for num in range(min_, max_)])


@pytest.fixture
def default_emitters():
    field = Field('field', text(1, 4, Static('FIELD')))
    multi = Field('field', text(1, 4, Static('MULTI')), repeat=num_range(1, 3))
    gate = Field('field', text(1, 4, Static('GATE')), gate=chance(0.6))
    multi_gate = Field('field', text(1, 4, Static('MULTIGATE')),
                       repeat=num_range(1, 3), gate=chance(0.6))
    return {
        'default': text(1, 4, Static('TEST')),
        'copy': CopyFields(field),
        'copy_multi': CopyFields(multi),
        'copy_gate': CopyFields(gate),
        'copy_multi_gate': CopyFields(multi_gate)
    }


@pytest.fixture
def facet_term_emitter():
    return text(1, 4, keyword(word(2, 5, LETTERS)))


@pytest.fixture
def count_terms_in_results():
    """Fixture: function for counting term occurrences in results."""
    def _flatten(values):
        flattened = []
        for value in values:
            if isinstance(value, (list, tuple)):
                flattened.extend(_flatten(value))
            elif value is not None:
                flattened.append(value)
        return flattened

    def _find_exact_match(key, value):
        return key == value

    def _find_match_in(key, value):
        return key in value

    def _count_terms_in_results(result, terms, term_exact_match):
        flattened = []
        try:
            _ = result.keys()
        except AttributeError:
            flattened = _flatten(result)
        else:
            for field_result in result.values():
                flattened.extend(_flatten(field_result))
        _find = _find_exact_match if term_exact_match else _find_match_in
        counts = {k: len([v for v in flattened if _find(k, v)]) for k in terms}
        return counts, flattened
    return _count_terms_in_results


# conftest.py contains these fixtures, employed in the below tests.
#     term_selection_sanity_check
#     vocabulary_sanity_check


# Tests

@pytest.mark.parametrize(
    'seed, which_emitter, repeat, gate, inject_chance, overwrite_chance,'
    'expected', [
        (999, 'default', None, None, 0, 0,
         ['TEST TEST TEST', 'TEST', 'TEST TEST TEST', 'TEST TEST TEST',
          'TEST TEST TEST', 'TEST TEST', 'TEST TEST', 'TEST', 'TEST TEST TEST',
          'TEST TEST']),
        (999, 'default', None, None, 1.0, 0,
         ['TEST TEST TE _zzz_ ST', 'TE _vvv_ ST', 'T _ccc_ EST TEST TEST',
          'TEST TEST _sss_  TEST', 'TEST TEST _sss_  TEST', 'TEST TE _rrr_ ST',
          'TEST TE _ppp_ ST', '_ppp_ TEST', 'TEST TEST TE _eee_ ST',
          'TEST  _zzz_ TEST']),
        (999, 'default', None, None, 1.0, 0.5,
         ['T _zzz_ EST TEST TEST', 'TE _vvv_ ST', 'TEST TE _ccc_ ST TEST',
          '_sss_', 'TEST TEST  _sss_ TEST', '_rrr_', 'T _ppp_ EST TEST',
          '_ppp_ TEST', '_eee_', '_zzz_ TEST TEST']),
        (999, 'default', None, None, 1.0, 0.75,
         ['T _zzz_ EST TEST TEST', 'TE _vvv_ ST', '_ccc_', '_sss_', '_sss_',
          'TEST  _rrr_ TEST', '_ppp_', '_ppp_', 'TEST TEST  _eee_ TEST',
          'TES _zzz_ T TEST']),
        (999, 'default', None, None, 1.0, 1.0,
         ['_zzz_', '_vvv_', '_ccc_', '_sss_', '_sss_', '_rrr_', '_ppp_',
          '_ppp_', '_eee_', '_zzz_']),
        (999, 'default', None, None, 0.75, 0.75,
         ['TEST TEST TEST', 'TE _zzz_ ST', '_vvv_', 'TEST TEST TEST', '_ccc_',
          'TES _sss_ T TEST', '_sss_ TEST TEST', '_rrr_', 'TEST TEST TEST',
          'TEST TEST']),
        (999, 'default', None, chance(0.5), 1.0, 1.0,
         [None, '_zzz_', None, None, '_vvv_', '_ccc_', None, '_sss_', None,
          None]),
        (999, 'default', None, chance(0), 1.0, 1.0,
         [None, None, None, None, None, None, None, None, None, None]),
        (999, 'default', Static(1), None, 0.75, 0.80,
         [['TEST TEST TEST'], ['_zzz_'], ['TEST TEST TEST'], ['_vvv_'],
          ['TEST TEST TEST'], ['_ccc_'], ['TEST T _sss_ EST'], ['TE _sss_ ST'],
          ['TEST TEST TEST'], ['TEST  _rrr_ TEST']]),
        (999, 'default', Static(2), None, 0, 0,
         [['TEST TEST TEST', 'TEST'], ['TEST TEST TEST', 'TEST TEST'],
          ['TEST TEST', 'TEST'], ['TEST TEST TEST', 'TEST'],
          ['TEST TEST TEST', 'TEST TEST TEST'], ['TEST', 'TEST TEST TEST'],
          ['TEST', 'TEST'], ['TEST TEST', 'TEST TEST TEST'],
          ['TEST', 'TEST TEST TEST'], ['TEST TEST TEST', 'TEST']]),
        (999, 'default', Static(2), None, 1.0, 0,
         [['TEST TEST _zzz_  TEST', 'TEST'],
          ['TEST TEST TEST', 'TEST TE _vvv_ ST'], ['TEST  _ccc_ TEST', 'TEST'],
          ['TEST TEST  _sss_ TEST', 'TEST'],
          ['TE _sss_ ST TEST TEST', 'TEST TEST TEST'],
          ['TEST', 'TEST TEST _rrr_  TEST'], ['TE _ppp_ ST', 'TEST'],
          ['TEST TEST', 'TEST T _ppp_ EST TEST'],
          ['TE _eee_ ST', 'TEST TEST TEST'],
          ['TEST TEST TEST', '_zzz_ TEST']]),
        (999, 'default', Static(2), None, 1.0, 0.75,
         [['TEST TEST _zzz_  TEST', 'TEST'], ['TEST TEST TEST', '_vvv_'],
          ['TEST TEST', '_ccc_'], ['_sss_', 'TEST'],
          ['_sss_', 'TEST TEST TEST'], ['_rrr_', 'TEST TEST TEST'],
          ['TEST', '_ppp_'], ['TEST T _ppp_ EST', 'TEST TEST TEST'],
          ['_eee_', 'TEST TEST TEST'], ['_zzz_', 'TEST']]),
        (999, 'default', Static(2), chance(0.8), 0.8, 0.8,
         [['TEST TEST _zzz_  TEST', 'TEST'], ['TEST TEST TEST', '_vvv_'], None,
          ['TEST TEST', 'TEST'], ['_ccc_', 'TEST'],
          ['TEST TEST TEST', 'TEST TEST TEST'], ['_sss_', 'TEST TEST TEST'],
          ['T _sss_ EST', 'TEST'], ['TES _rrr_ T TEST', 'TEST TEST TEST'],
          None]),

        # After this point the focus is on SearchFields that use a
        # CopyField emitter, since it isn't necessarily obvious how
        # the SearchField options interact when copying from an
        # existing field that might have different options.

        (999, 'copy', None, None, 1.0, 0,
         ['FI _zzz_ ELD FIELD FIELD', 'FIE _vvv_ LD',
          'FIELD FIELD FIE _ccc_ LD', 'FIEL _sss_ D FIELD FIELD',
          'FIELD FIEL _sss_ D FIELD', 'F _rrr_ IELD FIELD',
          'FIE _ppp_ LD FIELD', 'F _ppp_ IELD', 'FIELD FI _eee_ ELD FIELD',
          'FIELD FIE _zzz_ LD']),
        # If the SearchField is multi-valued but the source field is
        # not -- the SearchField repeats whatever single value the
        # source output and selects one repetition to inject a term
        # into or overwrite.
        (999, 'copy', Static(2), None, 1.0, 0.5,
         [['FIELD FIELD FIE _zzz_ LD', 'FIELD FIELD FIELD'],
          ['FIELD', '_vvv_'],
          ['FIELD FIELD FIELD', 'FIE _ccc_ LD FIELD FIELD'],
          ['_sss_', 'FIELD FIELD FIELD'],
          ['FIELD FI _sss_ ELD FIELD', 'FIELD FIELD FIELD'],
          ['FIELD FIELD', 'FIE _rrr_ LD FIELD'], ['FIELD FIELD', '_ppp_'],
          ['F _ppp_ IELD', 'FIELD'],
          ['FIELD FIEL _eee_ D FIELD', 'FIELD FIELD FIELD'],
          ['F _zzz_ IELD FIELD', 'FIELD FIELD']]),
        # If the SearchField is gated but the source field is not --
        # the SearchField just skips whatever value the source field
        # generated and emits None instead. This is fine.
        (999, 'copy', None, chance(0.5), 1.0, 0,
         [None, '_zzz_ FIELD', None, None, 'FIELD FIELD FIE _vvv_ LD',
          'FIELD F _ccc_ IELD', None, 'F _sss_ IELD', None, None]),
        # If the source field is gated but the SearchField is not -- no
        # output is generated if the source field output is None, and
        # no search term is generated. This should preserve the
        # integrity of whatever term weighting is used.
        (999, 'copy_gate', None, None, 1.0, 0,
         [None, 'GATE GATE GA _zzz_ TE', None, 'GA _vvv_ TE',
          'G _ccc_ ATE GATE GATE', 'GATE GATE _sss_  GATE', None,
          'GATE GATE _sss_  GATE', None, None]),
        (999, 'copy_gate', Static(2), None, 1.0, 0.5,
         [[None, None], ['GATE GATE _zzz_  GATE', 'GATE GATE GATE'],
          [None, None], ['GATE', '_vvv_'],
          ['GATE GATE GATE', 'GATE GATE  _ccc_ GATE'],
          ['GAT _sss_ E GATE GATE', 'GATE GATE GATE'], [None, None],
          ['_sss_', 'GATE GATE GATE'], [None, None], [None, None]]),
        (999, 'copy_gate', None, chance(0.5), 1.0, 0,
         [None, 'GATE GATE GA _zzz_ TE', None, None, 'GATE GATE  _vvv_ GATE',
          'G _ccc_ ATE GATE GATE', None, 'GATE GATE _sss_  GATE', None, None]),
        # If the source field is multi-valued but the SearchField is
        # not -- the SearchField behaves as though it *were* multi-
        # valued, copying the source exactly and injecting terms.
        (999, 'copy_multi', None, None, 1.0, 0,
         [['MULTI MULTI MUL _zzz_ TI'], ['MULTI', 'MULT _vvv_ I MULTI MULTI'],
          ['MULTI MULTI', 'M _ccc_ ULTI MULTI'], ['M _sss_ ULTI'],
          ['MULTI MULTI MULTI', 'MULTI MUL _sss_ TI'],
          ['MULTI MU _rrr_ LTI MULTI'], ['MULTI M _ppp_ ULTI MULTI'],
          ['_ppp_ MULTI'], ['MULTI MULTI', '_eee_ MULTI MULTI MULTI'],
          ['M _zzz_ ULTI']]),
        # If both the source field AND SearchField are multi-valued --
        # the complete source output is repeated as necessary, so each
        # resulting value is a list of lists. Terms are injected as
        # normal within the deepest list. You should avoid doing this,
        # in practice, since it likely isn't compatible with how your
        # Solr fields are actually configured.
        (999, 'copy_multi', Static(2), None, 1.0, 0.5,
         [[['_zzz_'], ['MULTI MULTI MULTI']],
          [['MULTI', 'MULTI MULTI MULTI'],
           ['M _vvv_ ULTI', 'MULTI MULTI MULTI']],
          [['MULTI MULTI', '_ccc_ MULTI MULTI'],
           ['MULTI MULTI', 'MULTI MULTI']],
          [['MULTI'], ['M _sss_ ULTI']],
          [['MULTI MULTI MULTI', 'MULTI MULTI'], ['_sss_', 'MULTI MULTI']],
          [['_rrr_'], ['MULTI MULTI MULTI']],
          [['MULTI MULTI MULTI'], ['MU _ppp_ LTI MULTI MULTI']],
          [['MULTI'], ['_ppp_']],
          [['MULTI MULTI', 'MULTI MULTI MULTI'], ['MULTI MULTI', '_eee_']],
          [['M _zzz_ ULTI'], ['MULTI']]]),
        (999, 'copy_multi', None, chance(0.5), 1.0, 0,
         [None, ['MUL _zzz_ TI', 'MULTI MULTI MULTI'], None, None,
          ['MULTI MULTI MULTI', 'MU _vvv_ LTI MULTI'],
          ['MUL _ccc_ TI MULTI MULTI'], None, ['M _sss_ ULTI'], None, None]),
        (999, 'copy_multi_gate', None, None, 1.0, 0,
         [None, ['MULTIGATE MULTIGATE MULTIGA _zzz_ TE'], None,
          ['MULTIGATE', 'MULTIGATE MULTI _vvv_ GATE MULTIGATE'],
          ['MULTIGATE  _ccc_ MULTIGATE', 'MULTIGATE MULTIGATE'],
          ['MUL _sss_ TIGATE'], None,
          ['MULTIGAT _sss_ E MULTIGATE MULTIGATE', 'MULTIGATE MULTIGATE'],
          None, None]),
        (999, 'copy_multi_gate', Static(2), None, 1.0, 0.5,
         [[None, None], [['_zzz_'], ['MULTIGATE MULTIGATE MULTIGATE']],
          [None, None],
          [['MULTIGATE', 'MULTIGATE MULTIGATE MULTIGATE'],
           ['MUL _vvv_ TIGATE', 'MULTIGATE MULTIGATE MULTIGATE']],
          [['MULTIGATE MULTIGATE', 'M _ccc_ ULTIGATE MULTIGATE'],
           ['MULTIGATE MULTIGATE', 'MULTIGATE MULTIGATE']],
          [['MULTIGATE'], ['MUL _sss_ TIGATE']],
          [None, None],
          [['MULTIGATE MULTIGATE MULTIGATE', 'MULTIGATE MULTIGATE'],
           ['_sss_', 'MULTIGATE MULTIGATE']], [None, None], [None, None]]),
        (999, 'copy_multi_gate', None, chance(0.5), 1.0, 0,
         [None, ['MULTIGATE MULTIGATE MULTIGA _zzz_ TE'], None, None,
          ['MULTIGATE MULTIGATE', 'MULTIGATE MULTI _vvv_ GATE'],
          ['MULTI _ccc_ GATE'], None,
          ['MULTIGATE MULTIGATE  _sss_ MULTIGATE', 'MULTIGATE MULTIGATE'],
          None, None]),
    ]
)
def test_searchfield_injection_and_caching(seed, which_emitter, repeat, gate,
                                           inject_chance, overwrite_chance,
                                           expected, default_emitters):
    default_emitter = default_emitters[which_emitter]
    search_term_emitter = Choice([f"_{v * 3}_" for v in LETTERS])
    source_fields = getattr(default_emitter, 'source', None)
    if source_fields:
        source_fields.do_method('seed', seed)
    field = schema.SearchField('test', default_emitter, repeat, gate, seed)
    field.configure_injection(search_term_emitter, inject_chance,
                              overwrite_chance)
    prev_expected = [None] + expected[:-1]
    for exp_val, exp_prev_val in zip(expected, prev_expected):
        if source_fields:
            _ = [f() for f in source_fields]
        assert exp_prev_val == field.previous
        assert field() == exp_val
    assert expected[-1] == field.previous


@pytest.mark.parametrize('seed, emitter, st_emitter, count, expected', [
    # This test covers some specific edge cases that have proven
    # problematic.

    # First: regarding blank values. Term injection does not happen for
    # any blank-equivalent values. Normally it's recommended that an
    # emitter just emit None rather than something like '' or [].
    (999, Static(''), Static('_term_'), 1, ''),

    # However, when an emitter emits something like a list, we do not
    # inspect the list values to check to see if at least one is not
    # blank. We treat [''] as a non-blank value, and we DO inject.
    (999, Static(['']), Static('_term_'), 1, ['_term_']),
    (999, Static(['', '']), Static('_term_'), 1, ['_term_', '']),
    (999, Static(['TEST', '', 'TEST']), Static('_term_'), 1,
     ['TEST', '', '_term_ TEST']),

    # This is to test a previously-occurring error with position
    # selection when injecting into a single-character string.
    (999, Static('A'), Static('_term_'), 1, 'A _term_'),

    # These last tests just show the difference in how term injection
    # happens when you have an emitter that emits single values called
    # multiple times, compared to the above examples where you have
    # an emitter that emits a list with each call.
    (999, Sequential(['', '']), Static('_term_'), 4, ['', '', '', '']),
    (999, Sequential(['', 'TEST']), Static('_term_'), 4,
     ['', 'TE _term_ ST', '', '_term_ TEST']),
    (999, Sequential(['A', 'B']), Static('_term_'), 4,
     ['A _term_', 'B _term_', 'A _term_', 'B _term_']),
])
def test_searchfield_injection_emitter_edge_cases(seed, emitter, st_emitter,
                                                  count, expected):
    field = schema.SearchField('test', emitter, rng_seed=seed)
    field.configure_injection(st_emitter, 1.0, 0)
    if count == 1:
        assert field() == expected
    else:
        assert [field() for _ in range(count)] == expected


def test_searchfield_call_before_configure(default_emitters):
    """When a SearchField is called before injection is fully
    configured, it emits values as though it were a regular Field
    (without term injection). All three properties (term_emitter,
    inject_chance, overwrite_chance) must be configured before term
    injection kicks in.
    """
    expected_before = [
        'TEST TEST TEST', 'TEST', 'TEST TEST TEST', 'TEST TEST TEST',
        'TEST TEST TEST', 'TEST TEST', 'TEST TEST', 'TEST', 'TEST TEST TEST',
        'TEST TEST'
    ]
    expected_after = [
        'TEST TEST TE _zzz_ ST', 'TE _vvv_ ST', 'T _ccc_ EST TEST TEST',
        'TEST TEST _sss_  TEST', 'TEST TEST _sss_  TEST', 'TEST TE _rrr_ ST',
        'TEST TE _ppp_ ST', '_ppp_ TEST', 'TEST TEST TE _eee_ ST',
        'TEST  _zzz_ TEST'
    ]
    emitter = default_emitters['default']
    field = schema.SearchField('test', emitter, rng_seed=999)
    assert [field() for _ in range(10)] == expected_before
    field.term_emitter = Choice([f"_{v * 3}_" for v in LETTERS])
    field.reset()
    assert [field() for _ in range(10)] == expected_before
    field.overwrite_chance = 0
    field.reset()
    assert [field() for _ in range(10)] == expected_before
    field.inject_chance = 100
    field.reset()
    assert [field() for _ in range(10)] == expected_after


def test_searchfield_terms_property():
    myterms = ['one', 'two', 'three', 'four', 'five']
    field = schema.SearchField('test', Static('TEST'), None, 100)
    assert field.terms is None
    field.term_emitter = Choice(myterms)
    assert field.terms == myterms


@pytest.mark.parametrize(
    'chance_type, init_value, set_value, exp_init_result, exp_init_weights,'
    'exp_set_result, exp_set_weights', [
        ('inject', 0.5, 0.6, 0.5, [0.5, 1.0], 0.6, [0.6, 1.0]),
        ('inject', -0.1, 2, 0, [0, 1.0], 1.0, [1.0, 1.0]),
        ('inject', 2, -0.1, 1.0, [1.0, 1.0], 0, [0, 1.0]),
        ('overwrite', 0.5, 0.6, 0.5, [0.5, 1.0], 0.6, [0.6, 1.0]),
        ('overwrite', -0.1, 2, 0, [0, 1.0], 1.0, [1.0, 1.0]),
        ('overwrite', 2, -0.1, 1.0, [1.0, 1.0], 0, [0, 1.0]),
    ]
)
def test_searchfield_chance_properties(chance_type, init_value, set_value,
                                       exp_init_result, exp_init_weights,
                                       exp_set_result, exp_set_weights):
    inject_kwargs = {
        'inject_chance': init_value if chance_type == 'inject' else 0,
        'overwrite_chance': init_value if chance_type == 'overwrite' else 0
    }
    propname = f"{chance_type}_chance"

    field = schema.SearchField('test', Static('TEST'))
    field.configure_injection(Static('test'), **inject_kwargs)
    assert getattr(field, propname) == exp_init_result
    if exp_init_weights is not None:
        assert field._weights[chance_type] == exp_init_weights
    setattr(field, propname, set_value)
    assert getattr(field, propname) == exp_set_result
    if exp_set_weights is not None:
        assert field._weights[chance_type] == exp_set_weights


def test_facetfield_assert__call__not_overridden():
    # Our tests of the FacetField class assume that we have NOT
    # overridden the `__call__` method -- meaning we don't have to test
    # caching behavior. This is basically a sentinal test; if anything
    # changes, this test fails.
    check_cls = schema.FacetField
    parents = check_cls.__bases__
    assert any(getattr(p, '__call__') == check_cls.__call__ for p in parents)


@pytest.mark.parametrize(
    'seed, repeat, gate, cardinality_function, numdocs, exp_cardinality,'
    'exp_facet_counts, exp_sample', [
        (999, None, None, schema.static_cardinality(5), 1000, 5,
         {'Af Zner': 606, 'Ucwo Md Uiuv': 311, 'Gos Gw Zfqb': 73, 'Cze': 9,
          'Exoy Ms': 1},
         ['Af Zner', 'Gos Gw Zfqb', 'Ucwo Md Uiuv', 'Cze', 'Exoy Ms',
          'Ucwo Md Uiuv', 'Af Zner', 'Ucwo Md Uiuv', 'Ucwo Md Uiuv',
          'Af Zner']),
        (999, None, None, schema.cardinality_factor(0.1, floor=1), 100, 10,
         {'Nbul': 51, 'Pw Xza Nu': 33, 'Gos Gw Zfqb': 7, 'Exoy Ms': 3,
          'Af Zner': 1, 'Cze': 1, 'Cx Oefu Fnhg': 1, 'Tg Cv Guh': 1,
          'Ucwo Md Uiuv': 1, 'Tdqm': 1},
         ['Nbul', 'Gos Gw Zfqb', 'Pw Xza Nu', 'Exoy Ms', 'Af Zner', 'Cze',
          'Cx Oefu Fnhg', 'Tg Cv Guh', 'Ucwo Md Uiuv', 'Tdqm', 'Pw Xza Nu',
          'Nbul', 'Pw Xza Nu', 'Pw Xza Nu', 'Nbul', 'Nbul', 'Pw Xza Nu',
          'Nbul', 'Pw Xza Nu', 'Pw Xza Nu']),
        (999, Static(2), None, schema.static_cardinality(5), 1000, 5,
         {'Af Zner': 1193, 'Ucwo Md Uiuv': 650, 'Gos Gw Zfqb': 142, 'Cze': 14,
          'Exoy Ms': 1},
         [['Af Zner', 'Gos Gw Zfqb'], ['Ucwo Md Uiuv', 'Cze'],
          ['Exoy Ms', 'Ucwo Md Uiuv'], ['Af Zner', 'Ucwo Md Uiuv'],
          ['Ucwo Md Uiuv', 'Af Zner'], ['Af Zner', 'Ucwo Md Uiuv'],
          ['Af Zner', 'Ucwo Md Uiuv'], ['Ucwo Md Uiuv', 'Af Zner'],
          ['Cze', 'Af Zner'], ['Af Zner', 'Ucwo Md Uiuv']]),
        (999, None, chance(0.5), schema.static_cardinality(5), 1000, 5,
         {'Af Zner': 321, 'Ucwo Md Uiuv': 173, 'Gos Gw Zfqb': 32, 'Cze': 6,
          'Exoy Ms': 1},
         [None, 'Af Zner', None, None, 'Gos Gw Zfqb', 'Ucwo Md Uiuv', None,
          'Cze', None, None, 'Exoy Ms', None, 'Ucwo Md Uiuv', 'Af Zner', None,
          None, 'Ucwo Md Uiuv', None, None, 'Ucwo Md Uiuv']),
        (999, num_range(1, 4), chance(0.66),
         schema.cardinality_factor(0.1), 1000, 100,
         {'Pcy': 106, 'Mi Nly Lr': 106, 'Lbz Pchl Zwp': 110, 'Exoy Ms': 96,
          'Gos Gw Zfqb': 77, 'Aoff Eve Xu': 84, 'Bm Qryr Zk': 86, 'Opo': 74,
          'Pj Cla Favv': 66, 'Fd': 48, 'Car': 61, 'Zb Jiub Qxb': 44,
          'Wcg Baxi Mcs': 39, 'Ik Qwdw': 39, 'Lg Xjt': 29, 'Zpfa': 30,
          'Lu': 36, 'Cx Oefu Fnhg': 19, 'Eovd': 21, 'Ln Fxsn': 17, 'Anck': 12,
          'Cze': 13, 'Vfh': 8, 'Wbtv Ge': 4, 'Ohn': 6, 'Vc Mduk': 2,
          'Vn Pla': 3, 'Hh Yql': 5, 'Yjk Uxgf': 6, 'Mwkl Ip Jul': 2, 'Lwi': 2,
          'Fvl': 1, 'Bjgt Iv': 1, 'Ogf Wswj': 1, 'Eqf Ylcg Cgay': 1,
          'Psr Sb Fco': 1, 'Ow': 1, 'Pn Junp Th': 1, 'Evox Caf Ddi': 1,
          'Gsn Xhbd Bbjk': 1, 'Icjt Sscq Th': 1, 'Homc Yt': 1,
          'Gzen Prn Iy': 1, 'Bs Xa': 1, 'Rrau': 1, 'Zs Esyw Tcg': 1, 'Lr': 1,
          'Zti': 1, 'Esyd Ma': 1, 'Ccp Imnt': 1, 'Mt Fc Gpm': 1, 'Kwta': 1,
          'Irar Ko': 1, 'Pw Xza Nu': 1, 'Jse': 1, 'Ku': 1, 'Teut Mwr Mnzi': 1,
          'Znri Gsv': 1, 'Ukbz Iez Dnh': 1, 'Ce Xqkb Ylx': 1, 'Okc': 1,
          'Zqhc': 1, 'Lwp Vcn Okk': 1, 'Dxjm': 1, 'Tdqm': 1, 'Jxt': 1,
          'Yrgc': 1, 'Bk Kqf': 1, 'Ug Dt Ktex': 1, 'Om Iqs Hk': 1,
          'Gp Uajb': 1, 'Ch': 1, 'Jas Xumt Hk': 1, 'Si': 1, 'Af Zner': 1,
          'Vl Uybj': 1, 'Ob': 1, 'Dkex Dnqb Nl': 1, 'Rae Merd Fm': 1,
          'Pn Yhe': 1, 'Sp': 1, 'Mwr Djez Dnoo': 1, 'Tg Cv Guh': 1,
          'Eiff Hcnx': 1, 'Kn': 1, 'Mbe': 1, 'Hkhq': 1, 'Lgox Irgb': 1,
          'Im Faby': 1, 'Fi Cdy Okmt': 1, 'Ku Iwbw Sgs': 1, 'Nbul': 1,
          'Wacm Afzd Lmly': 1, 'Zmy': 1, 'Ucwo Md Uiuv': 1, 'Xvpc Harb': 1,
          'Mte': 1, 'Kys Mzre Ahra': 1, 'Cch': 1, 'Lqb Dp Jx': 1},
         [None, ['Zb Jiub Qxb', 'Eovd', 'Lbz Pchl Zwp'], None, ['Pcy'],
          ['Fd', 'Bm Qryr Zk', 'Pj Cla Favv'],
          ['Cx Oefu Fnhg', 'Ohn', 'Exoy Ms'], None,
          ['Gos Gw Zfqb', 'Zpfa', 'Opo'], None, None]),
    ]
)
def test_facetfield_build_and_emit_values(seed, repeat, gate,
                                          cardinality_function, numdocs,
                                          exp_cardinality, exp_facet_counts,
                                          exp_sample, facet_term_emitter,
                                          count_terms_in_results,
                                          vocabulary_sanity_check,
                                          term_selection_sanity_check):
    ffield = schema.FacetField('test', facet_term_emitter, repeat, gate,
                               cardinality_function, seed)
    ffield.build_facet_values_for_docset(numdocs)
    result = [ffield() for _ in range(numdocs)]
    fcounts, flat_result = count_terms_in_results(result, ffield.terms, True)
    assert fcounts == exp_facet_counts
    assert list(exp_facet_counts.keys()) == ffield.terms
    assert result[:len(exp_sample)] == exp_sample
    vocabulary_sanity_check(ffield.terms, exp_cardinality)
    term_selection_sanity_check(flat_result, ffield.terms, True)


@pytest.mark.parametrize('cardinality, docs', [
    (1, 10),
    (1, 10000),
    (5, 1),
    (5, 10000),
    (10, 100),
])
def test_staticcardinality_function_output(cardinality, docs):
    func = schema.static_cardinality(cardinality)
    assert func(docs) == cardinality


@pytest.mark.parametrize('factor, floor, docs, expected', [
    (0.1, 10, 10, 10),
    (0.1, 10, 90, 10),
    (0.1, 5, 90, 9),
    (0.1, 10, 100, 10),
    (0.1, 10, 120, 12),
    (0.1, 10, 129, 13),
    (0.5, 10, 100, 50),
])
def test_cardinalityfactor_function_output(factor, floor, docs, expected):
    func = schema.cardinality_factor(factor, floor)
    assert func(docs) == expected


def test_benchmarkschema_addfield_field_categorization():
    fields = {
        'id': Field('id', id_(1, 10000)),
        'title': Field('title', Static('Title')),
        'author_facet': schema.FacetField('author_facet', Static('Author')),
        'year_facet': schema.FacetField('year_facet', Static('Year')),
        'meeting': Field('meeting', Static('Meeting'))
    }
    fields.update({
        'title_sr': schema.SearchField('title_sr',
                                       CopyFields(fields['title'])),
        'author_sr': schema.SearchField('author_sr',
                                        CopyFields(fields['author_facet'])),
        'meeting_sr': schema.SearchField('meeting_sr',
                                         CopyFields(fields['meeting']))
    })

    myschema = schema.BenchmarkSchema()
    myschema.add_fields(*fields.values())
    assert list(myschema.fields.values()) == list(fields.values())
    assert list(myschema.search_fields.values()) == [
        fields['title_sr'],
        fields['author_sr'],
        fields['meeting_sr']
    ]
    assert list(myschema.facet_fields.values()) == [
        fields['author_facet'],
        fields['year_facet']
    ]


def test_benchmarkschema_configure_check():
    search_term_emitter = Choice([f"_{v * 3}_" for v in LETTERS])
    myschema = schema.BenchmarkSchema(*[
        Field('id', id_(1, 10000)),
        Field('title', Static('Title')),
        schema.FacetField('author_facet', text(1, 4, word(2, 8, LETTERS)),
                          gate=chance(0.85)),
        schema.FacetField('pub_year_facet', num_range_string(1890, 2022)),
        Field('meeting', Static('Meeting'), gate=chance(0.1))
    ])
    fields = myschema.fields
    myschema.add_fields(*[
        schema.SearchField('title_sr', CopyFields(fields['title'])),
        schema.SearchField('author_sr', CopyFields(fields['author_facet'])),
        schema.SearchField('meeting_sr', CopyFields(fields['meeting']))
    ])
    assert myschema.search_terms is None
    assert myschema.search_term_emitter is None
    for ffield in myschema.facet_fields.values():
        assert ffield.terms is None
        assert ffield.emitter.items == [None]
    for sfield in myschema.search_fields.values():
        assert sfield.terms is None
        assert sfield.term_emitter is None

    myschema.configure(1000, search_term_emitter, term_doc_ratio=0.5,
                       overwrite_chance=0.5, rng_seed=999)
    assert myschema.search_terms is not None
    assert myschema.search_term_emitter == search_term_emitter
    for ffield in myschema.facet_fields.values():
        assert len(set(ffield.terms)) == ffield.cardinality_function(1000)
        assert ffield.emitter() in ffield.terms
    for sfield in myschema.search_fields.values():
        assert sfield.terms == myschema.search_terms
        assert sfield.term_emitter == search_term_emitter
        assert sfield.overwrite_chance == 0.5
    assert round(myschema.fields['author_sr'].inject_chance, 4) == 0.2267
    assert round(myschema.fields['title_sr'].inject_chance, 4) == 0.1925
    assert myschema.fields['meeting_sr'].inject_chance == 1.0


@pytest.mark.parametrize('td_ratio, max_per_field, expected', [
    (1.0, {'a': 1.0, 'b': 1.0, 'c': 1.0},
     {'a': 0.3333, 'b': 0.3333, 'c': 0.3333}),
    (0.5, {'a': 1.0, 'b': 1.0, 'c': 1.0},
     {'a': 0.1667, 'b': 0.1667, 'c': 0.1667}),
    (1.0, {'a': 0.01, 'b': 0.01, 'c': 0.01},
     {'a': 1.0, 'b': 1.0, 'c': 1.0}),
    (0.5, {'a': 0.01, 'b': 0.01, 'c': 0.01},
     {'a': 1.0, 'b': 1.0, 'c': 1.0}),
    (1.0, {'a': 0.01, 'b': 1.0, 'c': 1.0},
     {'a': 1.0, 'b': 0.495, 'c': 0.495}),
    (0.5, {'a': 0.01, 'b': 1.0, 'c': 1.0},
     {'a': 1.0, 'b': 0.245, 'c': 0.245}),
    (1.0, {'a': 0.3, 'b': 0.25, 'c': 1.0},
     {'a': 1.0, 'b': 1.0, 'c': 0.45}),
    (0.5, {'a': 0.3, 'b': 0.25, 'c': 1.0},
     {'a': 0.5556, 'b': 0.6667, 'c': 0.1667}),
    (1.0, {'a': 0.4, 'b': 0.4, 'c': 0.4},
     {'a': 0.8333, 'b': 0.8333, 'c': 0.8333}),
    (0.5, {'a': 0.4, 'b': 0.4, 'c': 0.4},
     {'a': 0.4167, 'b': 0.4167, 'c': 0.4167}),
    (1.0, {'a': 1/3, 'b': 1/3, 'c': 1/3},
     {'a': 1.0, 'b': 1.0, 'c': 1.0}),
    (2.0, {'a': 1/3, 'b': 1/3, 'c': 1/3},
     {'a': 1.0, 'b': 1.0, 'c': 1.0}),
    (2.0, {'a': 1.0, 'b': 1.0, 'c': 1.0},
     {'a': 0.6667, 'b': 0.6667, 'c': 0.6667}),
    (1.0, {'a': 0.2, 'b': 0.2, 'c': 1.0, 'd': 1.0},
     {'a': 1.0, 'b': 1.0, 'c': 0.3, 'd': 0.3}),
])
def test_benchmarkschema_inj_chances(td_ratio, max_per_field, expected):
    myschema = schema.BenchmarkSchema()
    inj_chances = myschema._get_inj_chance_per_field(td_ratio, max_per_field)
    assert {fn: round(val, 4) for fn, val in inj_chances.items()} == expected


@pytest.mark.parametrize(
    'seed, fields, searchfields, inject_chance, overwrite_chance, ndocs,'
    'exp_sterm_counts, exp_fterm_counts, exp_cards, exp_sample', [
        (999, [
            Field('id', id_(1, 10000)),
            Field('title', text(1, 6, Static('TITLE'))),
            schema.FacetField(
                'main_author',
                text(2, 5, word(3, 8, LETTERS.upper())),
                cardinality_function=schema.cardinality_factor(0.02, 1)
            ),
         ],
         {'title_search': 'title', 'main_author_search': 'main_author'},
         0.5, 0.5, 1000,
         {'_aaa_': 64, '_bbb_': 64, '_ccc_': 59, '_ddd_': 50, '_eee_': 60,
          '_fff_': 48, '_ggg_': 54, '_hhh_': 61, '_iii_': 52, '_jjj_': 56},
         {'main_author': {
             'BAFZN ERE': 369, 'UOWZ BJIUB QXBLUY': 276, 'RGCV CMDUKLB': 174,
             'XTCEX QKB YLXZ TILNFX': 109, 'XOYMST DQMT GCVGUH NBULCXO': 41,
             'THKSIBJ GTIVR RAU SPOHNZ': 14, 'TVGEE QFY LCGCGA YVFHL': 4,
             'CNXOP OAOFFEV': 1, 'RPN JUNPTHJ': 1,
             'XOGFWS WJD KEXDNQ BNLYJ': 1, 'REA HRAOMIQ': 1,
             'ZPCHLZW PZPF AMWKLI PJU': 1, 'LJA SXUM': 1, 'EFU FNHGPWX ZAN': 1,
             'TEXKU LQBDPJ': 1, 'SHKZ QHCHHY QLWB': 1, 'KUXGFK YSMZ': 1,
             'UCWOMD UIU VCZEGOS GWZFQ': 1, 'SES YWTCGIK QWDWM TEUGDTK': 1,
             'SNPC YMTFC GPME IFFH': 1
          }},
         {'main_author': 20},
         [{'id': 'b1', 'title': 'TITLE', 'main_author': 'RGCV CMDUKLB',
           'title_search': 'TITLE', 'main_author_search': 'RGCV CMDUKLB'},
          {'id': 'b2', 'title': 'TITLE TITLE TITLE TITLE TITLE',
           'main_author': 'BAFZN ERE',
           'title_search': 'TITLE TITLE TITLE  _bbb_ TITLE TITLE',
           'main_author_search': 'BAFZN E _jjj_ RE'},
          {'id': 'b3', 'title': 'TITLE TITLE TITLE TITLE TITLE',
           'main_author': 'XTCEX QKB YLXZ TILNFX',
           'title_search': 'TITLE TITLE TITLE TITLE TITLE',
           'main_author_search': 'XTCEX QKB YLXZ TILNFX'},
          {'id': 'b4', 'title': 'TITLE TITLE TITLE TITLE TITLE',
           'main_author': 'UOWZ BJIUB QXBLUY',
           'title_search': 'TITLE TITLE TITLE TITLE TITLE',
           'main_author_search': 'UOWZ BJIUB QXBLUY'},
          {'id': 'b5', 'title': 'TITLE TITLE TITLE TITLE',
           'main_author': 'XOYMST DQMT GCVGUH NBULCXO',
           'title_search': 'TITLE TITLE TITLE TITLE',
           'main_author_search': 'XOYMST DQMT GCVGUH NBULCXO'}],
         ),
        (999, [
            Field('id', id_(1, 10000)),
            Field('title', text(1, 3, Static('TITLE'))),
            schema.FacetField(
                'main_author',
                text(2, 4, word(3, 8, LETTERS.upper())),
                cardinality_function=schema.cardinality_factor(0.02, 1)
            ),
         ],
         {'title_search': 'title', 'main_author_search': 'main_author'},
         1.0, 0.5, 1000,
         {'_aaa_': 111, '_bbb_': 127, '_ccc_': 115, '_ddd_': 95, '_eee_': 113,
          '_fff_': 90, '_ggg_': 107, '_hhh_': 109, '_iii_': 107, '_jjj_': 87},
         {'main_author': {
             'UOWZ BJIUB': 369, 'ERE XOYMST DQMT': 276, 'HRAOMIQ SHKZ': 174,
             'QFY LCGCGA YVFHL': 109, 'QXBLUY RGCV CMDUKLB': 41,
             'GCVGUH NBULCXO EFU': 14, 'WJD KEXDNQ BNLYJ': 4,
             'LQBDPJ XOGFWS': 1, 'RPN JUNPTHJ': 1, 'QHCHHY QLWB TVGEE': 1,
             'GWZFQ BAFZN': 1, 'SES YWTCGIK QWDWM': 1, 'RAU SPOHNZ': 1,
             'TEUGDTK TEXKU': 1, 'ZPCHLZW PZPF': 1, 'AMWKLI PJU LJA': 1,
             'FNHGPWX ZAN': 1, 'SXUM THKSIBJ GTIVR': 1,
             'UCWOMD UIU VCZEGOS': 1, 'KUXGFK YSMZ REA': 1}},
         {'main_author': 20},
         [{'id': 'b1', 'title': 'TITLE', 'main_author': 'HRAOMIQ SHKZ',
           'title_search': 'TITLE', 'main_author_search': 'HRAOMIQ SHKZ'},
          {'id': 'b2', 'title': 'TITLE TITLE', 'main_author': 'UOWZ BJIUB',
           'title_search': 'TITLE TIT _bbb_ LE',
           'main_author_search': 'UOWZ BJI _jjj_ UB'},
          {'id': 'b3', 'title': 'TITLE TITLE',
           'main_author': 'QFY LCGCGA YVFHL', 'title_search': 'TITLE TITLE',
           'main_author_search': '_jjj_'},
          {'id': 'b4', 'title': 'TITLE', 'main_author': 'ERE XOYMST DQMT',
           'title_search': 'TI _iii_ TLE',
           'main_author_search': 'ERE XOYMST DQMT'},
          {'id': 'b5', 'title': 'TITLE TITLE',
           'main_author': 'QXBLUY RGCV CMDUKLB', 'title_search': 'TITLE TITLE',
           'main_author_search': 'QXB _hhh_ LUY RGCV CMDUKLB'}]
         ),
        (999, [
            Field('id', id_(1, 10000)),
            Field('title', text(1, 3, Static('TITLE')), gate=chance(0.75)),
            schema.FacetField(
                'main_author',
                text(2, 4, word(3, 8, LETTERS.upper())),
                cardinality_function=schema.cardinality_factor(0.02, 1),
                gate=chance(0.75),
            ),
            schema.FacetField(
                'year',
                num_range_string(1800, 2022),
                cardinality_function=schema.cardinality_factor(0.015, 1),
                gate=chance(0.8)
            ),
            Field('contributors', text(2, 4, word(3, 8, LETTERS.upper())),
                  gate=chance(0.4), repeat=num_range(1, 4)),
            Field('meeting', text(2, 4, word(3, 8, LETTERS.upper())),
                  gate=chance(0.01), repeat=num_range(1, 3))
         ],
         {'title_search': ['title'],
          'author_search': ['main_author', 'contributors'],
          'meeting_search': ['meeting']},
         1.0, 0.5, 1000,
         {'_aaa_': 110, '_bbb_': 121, '_ccc_': 113, '_ddd_': 91, '_eee_': 109,
          '_fff_': 85, '_ggg_': 102, '_hhh_': 104, '_iii_': 103, '_jjj_': 84},
         {'main_author': {
             'UOWZ BJIUB': 287, 'ERE XOYMST DQMT': 209, 'HRAOMIQ SHKZ': 128,
             'QFY LCGCGA YVFHL': 78, 'QXBLUY RGCV CMDUKLB': 30,
             'GCVGUH NBULCXO EFU': 10, 'WJD KEXDNQ BNLYJ': 4,
             'LQBDPJ XOGFWS': 1, 'RPN JUNPTHJ': 1, 'QHCHHY QLWB TVGEE': 1,
             'GWZFQ BAFZN': 1, 'SES YWTCGIK QWDWM': 1, 'RAU SPOHNZ': 1,
             'TEUGDTK TEXKU': 1, 'ZPCHLZW PZPF': 1, 'AMWKLI PJU LJA': 1,
             'FNHGPWX ZAN': 1, 'SXUM THKSIBJ GTIVR': 1,
             'UCWOMD UIU VCZEGOS': 1, 'KUXGFK YSMZ REA': 1},
          'year': {
              '1926': 361, '1908': 250, '1993': 132, '1977': 44, '1927': 10,
              '1858': 1, '1821': 1, '1976': 1, '1870': 1, '1987': 1, '1817': 1,
              '1829': 1, '2020': 1, '1973': 1, '1841': 1}},
         {'main_author': 20,
          'year': 15},
         [{'id': 'b1', 'title': None, 'main_author': None, 'year': '1926',
           'contributors': None, 'meeting': None, 'title_search': None,
           'author_search': None, 'meeting_search': None},
          {'id': 'b2', 'title': 'TITLE', 'main_author': 'HRAOMIQ SHKZ',
           'year': '1993', 'contributors': ['UCWOMD UIU VCZEGOS',
                                            'GWZFQ BAFZN', 'ERE XOYMST DQMT'],
           'meeting': None, 'title_search': ['TITLE'],
           'author_search': ['HRAOMIQ SHKZ', 'UCWOMD UIU VCZEGOS',
                             'GWZFQ BAFZN', 'ERE XOYMST DQMT'],
           'meeting_search': None},
          {'id': 'b3', 'title': None, 'main_author': None, 'year': None,
           'contributors': None, 'meeting': None, 'title_search': None,
           'author_search': None, 'meeting_search': None},
          {'id': 'b4', 'title': 'TITLE TITLE', 'main_author': 'UOWZ BJIUB',
           'year': '1908', 'contributors': None, 'meeting': None,
           'title_search': ['_bbb_'], 'author_search': ['_jjj_'],
           'meeting_search': None},
          {'id': 'b5', 'title': 'TITLE TITLE',
           'main_author': 'QFY LCGCGA YVFHL', 'year': '1977',
           'contributors': None, 'meeting': None,
           'title_search': ['TITLE TITLE'],
           'author_search': ['QFY LCGCGA YVFHL'], 'meeting_search': None},
          {'id': 'b6', 'title': 'TITLE', 'main_author': 'ERE XOYMST DQMT',
           'year': '1927', 'contributors': ['GCVGUH NBULCXO EFU'],
           'meeting': None, 'title_search': ['T _jjj_ ITLE'],
           'author_search': ['ERE XOYMST DQ _iii_ MT', 'GCVGUH NBULCXO EFU'],
           'meeting_search': None},
          {'id': 'b7', 'title': None, 'main_author': None, 'year': '1858',
           'contributors': None, 'meeting': None, 'title_search': None,
           'author_search': None, 'meeting_search': None},
          {'id': 'b8', 'title': 'TITLE TITLE',
           'main_author': 'QXBLUY RGCV CMDUKLB', 'year': '1821',
           'contributors': ['FNHGPWX ZAN', 'UOWZ BJIUB QXBLUY',
                            'RGCV CMDUKLB ZPCHLZW'],
           'meeting': None, 'title_search': ['TITL _hhh_ E TITLE'],
           'author_search': ['QXBLUY RGCV CMDUKLB', 'FNHGPWX ZAN',
                             'U _hhh_ OWZ BJIUB QXBLUY',
                             'RGCV CMDUKLB ZPCHLZW'],
           'meeting_search': None},
          {'id': 'b9', 'title': None, 'main_author': None, 'year': '1976',
           'contributors': None, 'meeting': None, 'title_search': None,
           'author_search': None, 'meeting_search': None},
          {'id': 'b10', 'title': None, 'main_author': None, 'year': None,
           'contributors': None, 'meeting': None, 'title_search': None,
           'author_search': None, 'meeting_search': None}]
         ),
    ]
)
def test_benchmarkschema_build_and_emit_values(seed, fields, searchfields,
                                               inject_chance, overwrite_chance,
                                               ndocs, exp_sterm_counts,
                                               exp_fterm_counts, exp_cards,
                                               exp_sample,
                                               count_terms_in_results,
                                               term_selection_sanity_check,
                                               vocabulary_sanity_check):
    search_term_emitter = Choice([f"_{v * 3}_" for v in LETTERS[:10]])
    sch = schema.BenchmarkSchema(*fields)
    for sfname, copynames in searchfields.items():
        if isinstance(copynames, list):
            copy_em = CopyFields([sch.fields[name] for name in copynames])
        else:
            copy_em = CopyFields(sch.fields[copynames])
        sch.add_fields(schema.SearchField(sfname, copy_em))

    sch.configure(ndocs, search_term_emitter, inject_chance, overwrite_chance,
                  seed)
    result = [sch() for _ in range(ndocs)]
    assert result[:len(exp_sample)] == exp_sample

    st_res = {k: [r[k] for r in result] for k in sch.search_fields.keys()}
    stcounts, flat_st_res = count_terms_in_results(st_res, sch.search_terms,
                                                   False)
    assert stcounts == exp_sterm_counts
    term_selection_sanity_check(flat_st_res, search_term_emitter.items, False)

    for fname, ffield in sch.facet_fields.items():
        exp_fcounts = exp_fterm_counts[fname]
        ft_res = [r[fname] for r in result]
        ftcounts, flat_res = count_terms_in_results(ft_res, ffield.terms, True)
        assert ftcounts == exp_fterm_counts[fname]
        assert list(exp_fcounts.keys()) == ffield.terms
        vocabulary_sanity_check(ffield.terms, exp_cards[fname])
        term_selection_sanity_check(flat_res, ffield.terms, True)
