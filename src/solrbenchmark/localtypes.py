"""Contains custom variables, etc. used locally for type hinting."""
import os
import sys
from typing import (
    Any, ClassVar, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple,
    Union
)

from fauxdoc.typing import StrEmitterLike

if sys.version_info >= (3, 8):
    from typing import Protocol, TypedDict
else:
    from typing_extensions import Protocol, TypedDict


# Definitions for various complex / compound types.

Number = Union[int, float]
PathLike = Union[str, 'os.PathLike[str]']
InjectVal = Union[str, List[Union[None, 'InjectVal']]]
FacetValueCountsReturn = Dict[str, List[Tuple[str, int]]]
FacetValueCountsArg = Mapping[str, Sequence[Tuple[str, int]]]
Stats = Dict[str, Number]
StatsWithUnits = Dict[str, Tuple[Number, str]]
StatsWithTimings = Dict[str, Union[Number, List[Number]]]
SearchStats = Dict[str, 'SearchSetResult']
RawEventTimings = List[Tuple[str, Number]]
CompiledEventTimings = Dict[str, List[Number]]


# TypedDict definitions (for specific dict formats).

class SearchResult(TypedDict):
    """Raw result from running the BenchmarkRunner.search method.

    Includes the full pysolr result, # hits, and qtime in milliseconds.
    """
    result: 'PysolrResultLike'
    hits: int
    qtime_ms: Number


class TermResult(TypedDict):
    """Result from one BenchmarkRunner search term test.

    Includes the test term, # hits, and qtime in milliseconds.
    """
    term: str
    hits: int
    qtime_ms: Number


class SearchSetResult(TypedDict):
    """Result from running BenchmarkRunner.run_searches method.

    I.e., this is the result from running one "set" of test searches.
    Includes a list of individual term results (timings for each term)
    and the average/total query times, in milliseconds.
    """
    total_qtime_ms: Number
    avg_qtime_ms: Number
    term_results: List[TermResult]


class BenchmarkLogReport(TypedDict):
    """Full report after running BenchmarkRunner tests."""
    ADD: StatsWithUnits
    COMMIT: StatsWithUnits
    INDEXING: StatsWithUnits
    SEARCH: Dict[str, StatsWithUnits]


class CompiledEventTimingsInfo(TypedDict):
    """Info compiled from a list of raw event timings."""
    timings: CompiledEventTimings
    totals: Stats
    averages: Stats


# Protocol definitions.

class ConfigDataLike(Protocol):
    """Is like a runner.ConfigData object.

    This must be a dataclass with a `config_id` attribute. Any other
    attributes or methods that store details about a config under test
    are fine.
    """
    __dataclass_fields__: ClassVar[Dict[Any, Any]]
    config_id: str


class PysolrResultLike(Protocol):
    """Is like a pysolr.Result object.

    We only care that the result is iterable and that it has both a
    `hits` attribute and a `qtime` attribute.
    """
    hits: int
    qtime: Number

    def __len__(self) -> int:
        ...

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        ...


class PysolrConnLike(Protocol):
    """Is like a pysolr.Solr object.

    We only care that the connection object has an `add` method for
    adding documents, a `commit` method for issuing a commit, and a
    `search` method for searching Solr.
    """

    def add(self,
            docs: Sequence[Mapping[str, Any]],
            commit: Optional[bool] = None,
            **kwargs: Any) -> str:
        ...

    def commit(self, **kwargs: Any) -> str:
        ...

    def search(self, q: str, **kwargs: Any) -> PysolrResultLike:
        ...


class ItemsStrEmitterLike(StrEmitterLike, Protocol):
    """String-emitting fauxdoc.Emitter using fauxdoc.mixins.ItemsMixin."""
    items: List[str]
