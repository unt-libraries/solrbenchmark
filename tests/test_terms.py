"""Contains tests for `terms` module."""
import pytest
from fauxdoc.emitters.choice import Choice
from fauxdoc.emitters.fixed import Sequential, Static
from fauxdoc.emitters.text import Word

from solrbenchmark import terms


# Fixtures and Test Data

# conftest.py contains these fixtures, employed in the below tests.
#     term_selection_sanity_check
#     vocabulary_sanity_check
#     phrases_sanity_check

LOREM_IPSUM = (
    'ad', 'adipiscing', 'aliqua', 'aliquip', 'amet', 'anim', 'aute',
    'cillum', 'commodo', 'consectetur', 'consequat', 'culpa', 'cupidatat',
    'deserunt', 'do', 'dolor', 'dolore', 'duis', 'ea', 'eiusmod', 'elit',
    'enim', 'esse', 'est', 'et', 'eu', 'ex', 'excepteur', 'exercitation',
    'fugiat', 'id', 'in', 'incididunt', 'ipsum', 'irure', 'labore',
    'laboris', 'laborum', 'lorem', 'magna', 'minim', 'mollit', 'nisi',
    'non', 'nostrud', 'nulla', 'occaecat', 'officia', 'pariatur',
    'proident', 'qui', 'quis', 'reprehenderit', 'sed', 'sint', 'sit',
    'sunt', 'tempor', 'ullamco', 'ut', 'velit', 'veniam', 'voluptate'
)


# Tests

# Note: For testing the TermChoice emitter, we have separate tests for
# emitting in batch versus one-at-a-time because
# fauxdoc.emitters.choice.Choice values will differ between the
# two versions, given the same seed. (This isn't a bug -- Choice picks
# the most efficient algorithm when you emit values, which can result
# in different output for a batch versus one-at-a-time.)

@pytest.mark.parametrize('seed, choice_emitter, expected', [
    (999, Choice(range(5)),
     [2, 0, 3, 4, 1, 3, 0, 4, 2, 2, 0, 3, 1, 3, 4, 0, 4, 0, 1, 2]),
    # The rng_seed provided to TermChoice.__init__ overrides the
    # existing choice_emitter rng_seed.
    (999, Choice(range(5), rng_seed=5000),
     [2, 0, 3, 4, 1, 3, 0, 4, 2, 2, 0, 3, 1, 3, 4, 0, 4, 0, 1, 2]),
    (999, Choice(range(10)),
     [2, 9, 6, 8, 0, 3, 4, 7, 5, 1, 7, 0, 8, 5, 4, 1, 7, 3, 7, 8]),
    (999, Choice(range(5), [90, 5, 3, 1, 1]),
     [0, 2, 1, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0]),
    (999, Sequential(range(5)),
     [2, 0, 3, 4, 1, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4]),
])
def test_termchoice_emit_once_as_batch(seed, choice_emitter, expected,
                                       term_selection_sanity_check):
    tc_emitter = terms.TermChoice(choice_emitter, rng_seed=seed)
    result = tc_emitter(len(expected))
    assert result == expected
    term_selection_sanity_check(result, choice_emitter.items, True)


@pytest.mark.parametrize('seed, choice_emitter, expected', [
    (999, Choice(range(5)),
     [2, 0, 3, 4, 1, 0, 4, 4, 4, 3, 3, 1, 2, 0, 1, 1, 2, 4, 0, 2]),
    # The rng_seed provided to TermChoice.__init__ overrides the
    # existing choice_emitter rng_seed.
    (999, Choice(range(5), rng_seed=5000),
     [2, 0, 3, 4, 1, 0, 4, 4, 4, 3, 3, 1, 2, 0, 1, 1, 2, 4, 0, 2]),
    (999, Choice(range(10)),
     [2, 9, 6, 8, 0, 3, 4, 7, 5, 1, 1, 9, 9, 8, 7, 7, 2, 5, 1, 3]),
    (999, Choice(range(5), [90, 5, 3, 1, 1]),
     [0, 2, 1, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0]),
    (999, Sequential(range(5)),
     [2, 0, 3, 4, 1, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4]),
])
def test_termchoice_emit_one_at_a_time(seed, choice_emitter, expected,
                                       term_selection_sanity_check):
    tc_emitter = terms.TermChoice(choice_emitter, rng_seed=seed)
    result = [tc_emitter() for _ in range(len(expected))]
    assert result == expected
    term_selection_sanity_check(result, choice_emitter.items, True)


@pytest.mark.parametrize('choice_emitter', [
    Choice(range(5)),
    Choice(range(10)),
    Sequential(range(20)),
])
def test_termchoice_reset(choice_emitter):
    tc_emitter = terms.TermChoice(choice_emitter, rng_seed=999)
    emit1 = (tc_emitter(50), tc_emitter(50))
    tc_emitter.reset()
    emit2 = (tc_emitter(50), tc_emitter(50))
    assert emit1[0] != emit1[1]
    assert emit1 == emit2


@pytest.mark.parametrize('seed, emitter, vocab_size, expected', [
    (999, Choice(LOREM_IPSUM), 10,
     ['id', 'qui', 'sed', 'anim', 'aute', 'elit', 'sint', 'commodo', 'laboris',
      'proident']),
    (999, Choice(LOREM_IPSUM, replace=False), 10,
     ['ea', 'et', 'in', 'qui', 'duis', 'culpa', 'aliqua', 'fugiat', 'veniam',
      'voluptate']),
    (999, Word(Static(2), Choice('abc')), 9,
     ['aa', 'ab', 'ac', 'ba', 'bb', 'bc', 'ca', 'cb', 'cc']),
    (999, Word(Choice(range(1, 5)), Choice('abcdef')), 20,
     ['b', 'c', 'd', 'e', 'f', 'ad', 'bb', 'bd', 'eb', 'afb', 'ceb', 'faf',
      'aabf', 'aebe', 'afdb', 'daec', 'dbea', 'dfce', 'eafd', 'ebff']),
    (999, Word(Choice(range(1, 5)),
               Choice('abcdef', weights=[25, 10, 10, 10, 25, 20])), 20,
     ['a', 'b', 'd', 'e', 'f', 'ab', 'ae', 'eb', 'afa', 'dea', 'ead', 'faf',
      'aaaf', 'aebe', 'afea', 'daea', 'daed', 'eafe', 'ebff', 'efde']),
])
def test_makevocabulary(seed, emitter, vocab_size, expected,
                        vocabulary_sanity_check):
    result = terms.make_vocabulary(emitter, vocab_size, rng_seed=seed)
    assert result == expected
    vocabulary_sanity_check(result, vocab_size)


@pytest.mark.parametrize('emitter, vocab_size', [
    (Choice(LOREM_IPSUM), 100),
    (Sequential(range(1, 11)), 11),
    (Word(Static(2), Choice('abc')), 10),
])
def test_makevocabulary_not_enough_unique(emitter, vocab_size):
    with pytest.raises(ValueError) as excinfo:
        terms.make_vocabulary(emitter, vocab_size)
    err_msg = str(excinfo.value)
    assert f"can only emit {emitter.num_unique_values}" in err_msg
    assert f"you requested {vocab_size}" in err_msg


@pytest.mark.parametrize('seed, emitter, ph_counts, expected', [
    (999, Choice(LOREM_IPSUM[:10]), [10, 5, 3, 2],
     ['cillum ad', 'anim cillum', 'commodo anim', 'ad consectetur',
      'aliqua commodo', 'cillum aliquip', 'cillum commodo', 'amet adipiscing',
      'adipiscing aliqua', 'consectetur aliqua', 'cillum ad commodo',
      'anim amet adipiscing', 'cillum aliquip cillum',
      'adipiscing aliqua anim', 'commodo ad consectetur',
      'cillum ad commodo anim', 'cillum commodo ad consectetur',
      'amet adipiscing cillum aliquip', 'cillum ad commodo anim amet',
      'adipiscing cillum aliquip cillum commodo']),
    (999, Choice('abcd'), [5, 3, 2],
     ['b a', 'd a', 'd b', 'd c', 'd d', 'c b a', 'd a d', 'd b d', 'b a d b',
      'd a d c']),
    (999, Choice('abcd'), [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
     ['d a', 'd a d', 'd a d c', 'd a d c b', 'd a d c b a', 'd a d c b a d',
      'd a d c b a d b', 'd a d c b a d b d', 'd a d c b a d b d d',
      'd a d c b a d b d d a']),
    (999, Choice('abcd', replace_only_after_call=True), [3, 3, 3],
     ['a c', 'b d', 'd b', 'a c b', 'b d a', 'd a c', 'a c b d', 'b a d c',
      'b c d a']),
])
def test_makephrases(seed, emitter, ph_counts, expected, phrases_sanity_check):
    phrases = terms.make_phrases(emitter, ph_counts, rng_seed=seed)
    assert phrases == expected
    phrases_sanity_check(phrases, ph_counts)


@pytest.mark.parametrize(
    'seed, emitter, vocab_size, ph_counts, exp_sterms, exp_result', [
        (999, Choice([str(n) for n in range(100)]), 20, None,
         ['7', '8', '9', '13', '18', '22', '25', '26', '31', '49', '57', '63',
          '70', '78', '79', '84', '87', '88', '98', '99', '18 98', '25 26',
          '25 79', '49 22', '57 63', '70 18', '70 26', '70 78', '78 57',
          '88 25', '25 26 57', '57 49 22', '63 25 79', '70 18 78', '70 26 70',
          '78 18 98', '49 22 70 26', '70 18 78 57', '70 78 18 98',
          '70 18 78 57 49'],
         ['63', '98', '57 63', '88', '9', '49', '57 49 22', '25', '31',
          '88 25', '7', '84', '18 98', '79', '13', '70 78', '18', '70 26 70',
          '70 18 78', '70 18', '26', '78', '25 26 57', '70 78 18 98', '87',
          '70', '49 22 70 26', '99', '22', '63 25 79', '57', '49 22', '8',
          '70 26', '25 26', '70 18 78 57', '78 57', '25 79', '78 18 98',
          '70 18 78 57 49', '57 63', '9', '78 57', '87', '79', '18', '57 63',
          '49', '57 63', '70 78', '13', '70 18 78 57 49', '22', '26', '87',
          '25 26', '26', '88 25', '70 18 78 57', '25']),
        (999, Choice(LOREM_IPSUM), 10, [5, 3, 2, 1],
         ['id', 'qui', 'sed', 'anim', 'aute', 'elit', 'sint', 'commodo',
          'laboris', 'proident', 'aute sed', 'sint qui', 'sint anim',
          'sint aute', 'sint sint', 'aute aute sed', 'sint qui sint',
          'sint anim sint', 'aute sed sint anim', 'sint qui sint aute',
          'sint qui sint aute aute'],
         ['sint qui', 'aute sed sint anim', 'sed', 'proident', 'sint',
          'laboris', 'id', 'sint anim sint', 'anim', 'aute', 'aute aute sed',
          'sint sint', 'commodo', 'elit', 'sint aute', 'sint anim', 'qui',
          'sint qui sint aute aute', 'aute sed', 'sint qui sint',
          'sint qui sint aute', 'sint anim', 'qui', 'sint sint', 'laboris',
          'commodo', 'sed', 'sint anim', 'aute', 'sint anim', 'sint aute',
          'qui', 'sint qui sint aute aute', 'sed', 'anim', 'laboris',
          'aute sed', 'anim', 'sint sint', 'sint qui sint aute']),
        (999, Word(Choice(range(1, 6)), Choice('abcdef')), 5, [5, 5, 5],
         ['c', 'afb', 'bde', 'eafd', 'aebef', 'bde c', 'afb afb', 'bde afb',
          'bde bde', 'eafd bde', 'bde c eafd', 'afb afb bde', 'bde afb afb',
          'bde afb bde', 'bde c aebef', 'bde c eafd bde', 'afb afb bde afb',
          'afb afb bde bde', 'bde bde c aebef', 'afb eafd aebef afb'],
         ['afb afb bde', 'bde bde c aebef', 'bde', 'c', 'eafd bde', 'afb afb',
          'bde bde', 'eafd', 'aebef', 'afb afb bde bde', 'bde afb',
          'bde c eafd bde', 'bde c aebef', 'bde c', 'afb', 'bde afb bde',
          'bde afb afb', 'bde c eafd', 'afb afb bde afb', 'afb eafd aebef afb',
          'bde c eafd', 'c', 'bde afb afb', 'bde afb', 'bde c', 'afb',
          'bde c eafd', 'eafd', 'bde c eafd', 'bde afb afb', 'afb',
          'afb eafd aebef afb', 'bde', 'eafd', 'bde afb', 'eafd bde', 'eafd',
          'bde afb bde', 'bde bde c aebef', 'bde'])
    ]
)
def test_makesearchtermemitter(seed, emitter, vocab_size, ph_counts,
                               exp_sterms, exp_result, vocabulary_sanity_check,
                               phrases_sanity_check,
                               term_selection_sanity_check):
    stem = terms.make_search_term_emitter(emitter, vocab_size, ph_counts, seed)
    result = stem(len(exp_result))
    assert stem.items == exp_sterms
    assert result == exp_result
    if ph_counts is None:
        ph_counts = terms._default_phrase_counts(vocab_size)
    vocabulary_sanity_check(stem.items[:vocab_size], vocab_size)
    phrases_sanity_check(stem.items[vocab_size:], ph_counts)
    term_selection_sanity_check(result, stem.items, True)
