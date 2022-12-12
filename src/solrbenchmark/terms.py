"""Create sets of terms (facets, search terms) for benchmark tests."""
from typing import Any, List, Optional, Sequence

from fauxdoc.emitter import Emitter
from fauxdoc.emitters.choice import Choice, gaussian_choice
from fauxdoc.emitters.fixed import Static
from fauxdoc.emitters.text import Text
from fauxdoc.mixins import ItemsMixin, RandomWithChildrenMixin
from fauxdoc.typing import EmitterLike, StrEmitterLike
from solrbenchmark.localtypes import ItemsStrEmitterLike


class TermChoice(ItemsMixin, RandomWithChildrenMixin, Emitter):
    """Ensures all choices are selected once before repeating.

    This is meant to wrap a fauxdoc.emitters.Choice instance that does
    not emit globally unique values. Whereas such an emitter can repeat
    choices at any time, this will force it to emit each possible
    choice once before it can repeat. At that point it reverts to the
    default behavior for the wrapped emitter.

    This is useful when we want to ensure all terms will appears in a
    document set, such as for search and facet terms. Under normal
    circumstances, with weighting based on a probability distribution,
    there is a long tail of terms that may not appear in your document
    set at all when chosen at random. If you've (e.g.) created sets of
    facet values using target cardinalities, then each of your facet
    values must be selected at least once to give the facet that target
    cardinality.

    Caveats:
    - If your document set is not significantly larger than your
      available term set, then terms chosen will not AT ALL reflect the
      term weighting / distribution you've seleted. E.g., given a
      single-valued facet field, if you have 1000 facet terms and 1000
      documents, then each term will appear once in the document set.
    - The initial run through all the choices creates an artificial
      situation, where the first N documents will have unique terms
      from that term set. For running benchmark tests, I don't *think*
      this is a problem, but it does mean that your "long tail" terms
      end up appearing in sequential documents. We could maybe get
      around this by shuffling the documents before indexing them, but
      I don't think that's necessary.

    Attributes:
        rng: See fauxdoc.mixins.RandomWithChildrenMixin.rng.
        rng_seed: See fauxdoc.mixins.RandomWithChildrenMixin.rng_seed.
        emitters: See fauxdoc.mixins.RandomWithChildrenMixin.emitters.
        items: The list of terms available to be chosen, pulled from
            the wrapped emitter. See fauxdoc.mixins.ItemsMixin.items.
        emits_unique_values: See
            fauxdoc.emitter.Emitter.emits_unique_values.
        num_unique_values: See
            fauxdoc.mixins.ItemsMixin.num_unique_values.
        choice_emitter: The wrapped emitter, supplied on initialization
            (should be a fauxdoc.emitters.Choice instance or similar).
    """

    def __init__(self,
                 choice_emitter: ItemsStrEmitterLike,
                 rng_seed: Any = None) -> None:
        """Inits a TermChoice instance.

        Args:
            choice_emitter: See `choice_emitter` attribute.
            rng_seed: (Optional.) See `rng_seed` attribute.
        """
        super().__init__(
            children={
                'choice': choice_emitter,
                'unique': Choice(
                    choice_emitter.items,
                    weights=getattr(choice_emitter, 'weights', None),
                    replace=False,
                    replace_only_after_call=False,
                    noun=getattr(choice_emitter, 'noun', None)
                )
            },
            items=choice_emitter.items,
            rng_seed=rng_seed
        )

    @property
    def emits_unique_values(self) -> bool:
        """True if this emitter only emits unique values."""
        return False

    @property
    def choice_emitter(self) -> ItemsStrEmitterLike:
        """The wrapped choice emitter supplied on initialization.

        See the `choice_emitter` attribute.
        """
        return self._emitters['choice']

    def reset(self) -> None:
        """Resets state.

        Note that, when a TermChoice instance is reset, it will again
        emit the full list of unique terms before it begins repeating
        them.
        """
        super().reset()
        self._active_emitter = self._emitters['unique']

    def seed(self, rng_seed: Any) -> None:
        """See superclass."""
        super().seed(rng_seed)

    def emit(self) -> str:
        """Selects and returns the next term.

        Each possible term from `choice_emitter` is emitted before
        terms can repeat. Terms are emitted using whatever weighting
        has been assigned to `choice_emitter`.
        """
        try:
            return self._active_emitter()
        # A ValueError is raised when the active (unique) emitter runs
        # out of values. At this point all choices have been emitted
        # once, and we can switch over to the normal Choice emitter
        # behavior.
        except ValueError:
            self._active_emitter = self.choice_emitter
            return self._active_emitter()

    def emit_many(self, number: int) -> List[str]:
        """Selects and returns the next `number` terms.

        Each possible term from `choice_emitter` is emitted before
        terms can repeat. Terms are emitted using whatever weighting
        has been assigned to `choice_emitter`.

        Args:
            number: An int representing the number of desired terms.

        Returns:
            A list of `number` chosen terms.
        """
        try:
            return self._active_emitter(number)
        # A ValueError is raised when the active (unique) emitter runs
        # out of values. At this point all choices have been emitted
        # once, and we can switch over to the normal Choice emitter
        # behavior.
        except ValueError:
            unique_remaining = self._active_emitter.num_unique_values
            result = self._active_emitter(unique_remaining)
            self._active_emitter = self.choice_emitter
            result.extend(self._active_emitter(number - unique_remaining))
            return result


def _force_make_unique_values(emitter: EmitterLike,
                              num_desired: int) -> List[Any]:
    """Returns a list of unique values from an emitter.

    The supplied emitter may be something like fauxdoc.emitters.Text
    that does not have a way to guarantee unique values, but in this
    case its `num_unique_values` must show that it can emit the desired
    number of unique values. If not, it raises a ValueError.
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


def make_vocabulary(word_emitter: StrEmitterLike,
                    vocab_size: int,
                    rng_seed: Any = None) -> List[str]:
    """Uses an emitter to create a certain number of unique words.

    A "word" is a string that does not contain word-separator
    characters (i.e., spaces).

    This function *guarantees* unique words, even if `word_emitter` has
    a chance of generating duplicate words.

    Args:
        word_emitter: A fauxdoc.emitter.Emitter-like object that emits
            word strings. If it does guarantee emitting unique words,
            then its `num_unique_values` attribute must show that it
            can emit at least enough unique words to satisfy the
            desired vocabulary size. Raises a ValueError if it does
            not.
        vocab_size: An int representing how many vocabulary words to
            generate.
        rng_seed: (Optional.) The RNG seed value for `word_emitter`, to
            use for generating words. Default is None.

    Returns:
        A list of `vocab_size` unique vocabulary words, generated using
        the supplied `word_emitter`. Words are sorted by length and
        then alphabetically -- helpful for applying a weighting curve
        based on length, where shorter words are most heavily weighted.
    """
    try:
        word_emitter.seed(rng_seed)
    except AttributeError:
        pass
    word_emitter.reset()
    vocab = _force_make_unique_values(word_emitter, vocab_size)
    return sorted(vocab, key=lambda word: (len(word), word))


def make_phrases(word_chooser: StrEmitterLike,
                 phrase_counts: Sequence[int],
                 rng_seed: Any = None) -> List[str]:
    """Creates unique phrases of words chosen by `word_chooser`.

    Each "phrase" is a string of words, where each word is separated by
    a space.

    Args:
        word_chooser: A fauxdoc.emitter.Emitter-like object that emits
            word strings. Ideally this would be one that chooses from
            a set of pre-generated words, but it could be one that
            generates new words. Whatever the case, the number of
            unique words it can emit should satisfy the
            `phrase_word_sizes` requirements so that all phrases are
            unique. (If you want 100 2-word phrases, you need at least
            10 unique words (10^2 => 100).) Raises a ValueError if it
            does not.
        phrase_counts: A sequence of integers indicating how many
            phrases of various word-lengths you want, starting with
            2-word phrases. E.g., [50, 30, 16, 4] indicates you want 50
            2-word phrases, 30 3-word phrases, 16 4-word phrases, and
            4 5-word phrases.
        rng_seed: (Optional.) An RNG seed to use for generating
            phrases. Default is None.

    Returns:
        A list of phrase strings. The number of phrases of certain word
        sizes matches the supplied `phrase_counts` argument.
        Phrases are sorted by the number of words, by phrase string
        length, and then alphabetically -- helpful for applying a
        weighting curve based on length, where shorter phrases are
        most heavily weighted.
    """
    phrases = []
    for i, num_wanted in enumerate(phrase_counts):
        term_em = Text(Static(i + 2), word_chooser, rng_seed=rng_seed)
        new_terms = _force_make_unique_values(term_em, num_wanted)
        phrases.extend(sorted(new_terms, key=lambda v: (len(v), v)))
    return phrases


def _default_phrase_counts(vocab_size: int) -> List[int]:
    """Returns a sensible list of phrase counts based on vocab_size."""
    default_phrase_size_factors = (0.5, 0.3, 0.16, 0.04)
    return [round(vocab_size * fact) for fact in default_phrase_size_factors]


def make_search_term_emitter(word_emitter: StrEmitterLike,
                             vocab_size: int = 50,
                             phrase_counts: Optional[Sequence[int]] = None,
                             rng_seed: Any = None) -> TermChoice:
    """Makes an emitter to use for adding search terms to docsets.

    This automatically creates terms and configures a TermChoice
    emitter for you to use with a schema.BenchmarkSchema for injecting
    search terms into your document set. It's based on the following
    assumptions.
    - You want a concrete set of searchable terms consisting of N
      1-word terms plus (optionally) varying numbers of multi-word
      terms. Your 1-word terms set doubles as the vocabulary for your
      multi-word terms.
    - You want all terms to occur in the document set at least once,
      even the ones at the low ends of the distribution curve.
    - For best results, word lengths for words that `word_emitter`
      emits should be weighted with a distribution curve that peaks at
      the appropriate average number of letters-per-word for the
      language you're approximating. For English, this would be ~4
      letters per word. (Ultimately, this is controlled by the
      `word_emitter` you use.) When sorted by word length, the midpoint
      of the word list should represent the peak of the distribution.
    - To make multi-word terms, words are chosen from your vocabulary
      using a gaussian distribution where the peak (mu) is 0.5 * your
      vocab size. This helps ensure that words chosen for multi-word
      terms reflect the correct frequencies.
    - The complete set of terms gets distributed throughout a docset
      using a gaussian distribution where the peak (mu) is still 0.5 *
      your vocab size, and the width (sigma) is 0.4 * your total number
      of terms. Term choices will approximately reflect the most
      frequently-occurring words while ensuring multi-word terms are
      still sufficiently represented.

    If any of the above assumptions or behaviors are incorrect or not
    appropriate for your use case, then you should generate your terms
    and TermChoice emitter manually.

    Args:
        word_emitter: A fauxdoc.emitter.Emitter-like object that
            generates word strings. This must be able to emit enough
            unique words to satisfy `vocab_size` (raises a ValueError
            if not).
        vocab_size: (Optional.) An int representing how many total
            vocabulary words you want. Each word is both a potential
            1-word term and a candidate for appearing in a multi-word
            term in the resulting term set.
        phrase_counts: (Optional.) A sequence of integers indicating
            how many phrases of various word-lengths you want in your
            term set, starting with 2-word terms. If not supplied, a
            default is generated based on fractions of the total
            `vocab_size`:
                - 0.5 * vocab_size (2-word terms)
                - 0.3 * vocab_size (3-word terms)
                - 0.16 * vocab_size (4-word terms)
                - 0.04 * vocab_size (5-word terms)
        rng_seed: (Optional.) An RNG seed to use for generating terms
            (both vocabulary words and phrases). Default is None.

    Returns:
        A TermChoice emitter wrapping a Choice emitter that selects
        from the generated set of search terms, weighted using a
        gaussian distribution curve.
    """
    if phrase_counts is None:
        phrase_counts = _default_phrase_counts(vocab_size)
    vocab = make_vocabulary(word_emitter, vocab_size, rng_seed)
    # mu and sigma need to be scaled based on the vocab_size to ensure
    # a reasonable distribution. Appropriateness of results depends on
    # the distribution of word lengths in `vocab`, so this may need
    # tweaking or rethinking. We assume that, since `vocab` is sorted
    # by word length, the midpoint represents the peak of the intended
    # distribution.
    v_em = gaussian_choice(vocab, mu=vocab_size * 0.5, sigma=vocab_size * 0.2)
    sterms = vocab + make_phrases(v_em, phrase_counts, rng_seed)
    nterms = len(sterms)
    t_em = gaussian_choice(sterms, mu=vocab_size * 0.5, sigma=nterms * 0.4)
    return TermChoice(t_em, rng_seed)
