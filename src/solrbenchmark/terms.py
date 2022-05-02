"""
Create sets of terms (facets, search terms) to use in benchmark tests.
"""
from solrfixtures.mathtools import clamp
from solrfixtures.emitter import Emitter
from solrfixtures.emitters.choice import Choice, chance, gaussian_choice
from solrfixtures.emitters.fixed import Static
from solrfixtures.emitters.text import Text
from solrfixtures.group import ObjectMap
from solrfixtures.mixins import ItemsMixin, RandomMixin


class TermChoice(ItemsMixin, RandomMixin, Emitter):
    """Emitter that ensures all terms from a term set get chosen."""

    def __init__(self, choice_emitter, rng_seed=None):
        self._emitters = ObjectMap({})
        self.choice_emitter = choice_emitter
        self.unique_emitter = Choice(
            choice_emitter.items,
            weights=getattr(choice_emitter, 'weights', None),
            replace=False,
            replace_only_after_call=False,
            noun=getattr(choice_emitter, 'noun', None)
        )
        super().__init__(rng_seed=rng_seed)

    @property
    def choice_emitter(self):
        return self._emitters['choice']

    @choice_emitter.setter
    def choice_emitter(self, choice_emitter):
        self._emitters['choice'] = choice_emitter

    @property
    def unique_emitter(self):
        return self._emitters['unique']

    @unique_emitter.setter
    def unique_emitter(self, unique_emitter):
        self._emitters['unique'] = unique_emitter

    @property
    def items(self):
        return self._emitters['choice'].items

    def reset(self):
        super().reset()
        self._emitters.setattr('rng_seed', self.rng_seed)
        self._emitters.do_method('reset')
        self.active_emitter = self.unique_emitter

    def seed(self, rng_seed):
        super().seed(rng_seed)
        self._emitters.do_method('seed', self.rng_seed)

    def emit(self):
        try:
            return self.active_emitter()
        except ValueError:
            self.active_emitter = self.choice_emitter
            return self.active_emitter()

    def emit_many(self, number):
        try:
            return self.active_emitter(number)
        except ValueError:
            unique_remaining = self.active_emitter.num_unique_values
            result = self.active_emitter(unique_remaining)
            self.active_emitter = self.choice_emitter
            result.extend(self.active_emitter(number - unique_remaining))
            return result


def _force_emit_unique_values(emitter, num_desired):
    """Gets a list of unique values from an emitter.

    First this tries to sanity check whether the emitter will emit the
    number of desired unique values and raises a ValueError if not.
    """
    if emitter.emits_unique_values:
        return emitter(num_desired)
    max_unique = emitter.num_unique_values
    if max_unique is not None and max_unique < num_desired:
        raise ValueError(
            f"The provided emitter can only emit {max_unique} values, but you "
            f"requested {num_desired}. You must pass an emitter that emits AT "
            f"LEAST enough unique values to satisfy your requirement."
        )
    values = set()
    num = 0
    while num < num_desired:
        values |= set(emitter(num_desired - num))
        num = len(values)
    return list(values)


def make_vocabulary(word_emitter, vocab_size, rng_seed=None):
    """Returns a list containing `vocab_size` unique words."""
    try:
        word_emitter.seed(rng_seed)
    except AttributeError:
        pass
    word_emitter.reset()
    vocab = _force_emit_unique_values(word_emitter, vocab_size)
    return sorted(vocab, key=lambda word: (len(word), word))


def make_phrases(word_chooser, phrase_words_sizes, rng_seed=None):
    """Returns a list of phrases with words chosen by word_chooser.

    Use `phrase_words_sizes` to indicate how many phrases of various
    word-lengths you want. E.g., [50, 30, 16, 4] indicates:
        - 50 2-word phrases
        - 30 3-word phrases
        - 16 4-word phrases
        - 4 5-word phrases
    """
    phrases = []
    for i, num_wanted in enumerate(phrase_words_sizes):
        term_em = Text(Static(i + 2), word_chooser, rng_seed=rng_seed)
        new_terms = _force_emit_unique_values(term_em, num_wanted)
        phrases.extend(sorted(new_terms, key=lambda v: (len(v), v)))
    return phrases


def _default_phrase_counts(vocab_size):
    default_phrase_size_factors = (0.5, 0.3, 0.16, 0.04)
    return [round(vocab_size * fact) for fact in default_phrase_size_factors]


def make_search_term_emitter(word_emitter, vocab_size=50,
                             phrase_nterms_sizes=None, rng_seed=None):
    """Makes a set of search terms and returns search term emitter."""
    if phrase_nterms_sizes is None:
        phrase_nterms_sizes = _default_phrase_counts(vocab_size)
    vocab = make_vocabulary(word_emitter, vocab_size, rng_seed)
    v_em = gaussian_choice(vocab, mu=vocab_size * 0.5, sigma=vocab_size * 0.2)
    sterms = vocab + make_phrases(v_em, phrase_nterms_sizes, rng_seed)
    nterms = len(sterms)
    t_em = gaussian_choice(sterms, mu=nterms * 0.5, sigma=nterms * 0.4)
    return TermChoice(t_em, rng_seed)
