"""Contains custom variables, etc. used locally for type hinting."""
import os
from typing import (
    Any, Dict, Iterator, List, Mapping, Sequence, Tuple, Union
)

from fauxdoc.typing import StrEmitterLike

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol


Number = Union[int, float]
PathLike = Union[str, bytes, os.PathLike]
FacetValueCountsReturn = Dict[str, List[Tuple[str, int]]]
FacetValueCountsArg = Mapping[str, Sequence[Tuple[str, int]]]
TermResultsArg = Sequence[Mapping[str, Union[Number, str]]]
SearchReturn = Dict[str, Union['PysolrResultLike', Number]]
RunSearchesReturn = Dict[str, Union[Number, Dict[str, Union[str, Number]]]]
TimingDict = Dict[str, Tuple[Number, str]]
BenchmarkLogReport = Dict[str, Union[TimingDict, Dict[str, TimingDict]]]


# Protocols defined below.

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
            commit: bool = None,
            **kwargs: Any) -> str:
        ...

    def commit(self, **kwargs: Any) -> str:
        ...

    def search(self, q: str, **kwargs: Any) -> PysolrResultLike:
        ...


class ItemsStrEmitterLike(StrEmitterLike, Protocol):
    """String-emitting fauxdoc.Emitter using fauxdoc.mixins.ItemsMixin."""
    items: List[str]
