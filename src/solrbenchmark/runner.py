"""Contains classes for running benchmarking tests and compiling stats."""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Type, TypeVar

from solrbenchmark.localtypes import (
    BenchmarkLogReport, CompiledEventTimingsInfo, ConfigDataLike, PathLike,
    PysolrConnLike, RawEventTimings, SearchResult, SearchSetResult,
    SearchStats, Stats, StatsWithTimings, TermResult
)

from solrbenchmark.docs import DocSet
import ujson


C = TypeVar('C', bound='ConfigData')
B = TypeVar('B', bound='BenchmarkLog')
R = TypeVar('R', bound='BenchmarkRunner')


@dataclass
class ConfigData:
    """Stores information about a configuration under test.

    This a dataclass meant to help you store structured information
    about benchmark test configurations. Use this to keep track of what
    variables under test produced what results. Note that data values
    are all strings, and the structure of each string is up to you.

    Attributes:
        config_id: Str that uniquely identifies a configuration.
        solr_version: Str specifying the Solr version under test.
        solr_caches: Str detailing how Solr caches are configured for a
            test run.
        solr_conf: Str that outlines any other pertinent details
            (besides caches) about the solrconfig.xml under test.
        solr_schema: Str that outlines any pertinent details about the
            schema.xml or managed_schema under test.
        os: Str that identifies the OS, version, etc. used in testing.
        os_memory: Str detailing the OS memory available to Solr during
            a test run.
        jvm_memory: Str detailing relevant JVM heap memory settings
            (max heap, min heap, etc.) used during a test run.
        jvm_settings: Str detailing other JVM settings (besides heap)
            relevant to a test run.
        collection_size: Str that identifies how large the collection
            under test is -- number of documents or approximate size on
            disk.
        notes: Str that contains any notes about a test configuration
            not already covered by the other data values.
    """

    config_id: str
    solr_version: Optional[str] = None
    solr_caches: Optional[str] = None
    solr_conf: Optional[str] = None
    solr_schema: Optional[str] = None
    os: Optional[str] = None
    os_memory: Optional[str] = None
    jvm_memory: Optional[str] = None
    jvm_settings: Optional[str] = None
    collection_size: Optional[str] = None
    notes: Optional[str] = None

    def derive(self: C, config_id: str, **kwargs: Optional[str]) -> C:
        """Returns a new ConfigData instance copied from this one.

        If an attribute value is not provided in kwargs, that attribute
        value is copied from the old instance. This lets you create new
        configurations that only change one variable more quickly and
        easily.

        All values except `config_id` are optional.

        Args:
            config_id: A new ID str that will uniquely identify the new
                ConfigData object.
            solr_version: (Optional.) See `solr_version` attribute.
            solr_caches: (Optional.) See `solr_caches` attribute.
            solr_conf: (Optional.) See `solr_conf` attribute.
            solr_schema: (Optional.) See `solr_schema` attribute.
            os: (Optional.) See `os` attribute.
            os_memory: (Optional.) See `os_memory` attribute.
            jvm_memory: (Optional.) See `jvm_memory` attribute.
            jvm_settings: (Optional.) See `jvm_settings` attribute.
            collection_size: (Optional.) See `collection_size`
                attribute.
            notes: (Optional.) See `notes` attribute.
        """
        new_obj = replace(self)
        new_obj.config_id = config_id
        for arg, val in kwargs.items():
            setattr(new_obj, arg, val)
        return new_obj


def compose_log_json_filepath(basepath: PathLike,
                              docset_id: str,
                              config_id: str) -> Path:
    """Returns the filepath for a log file from a docset & config id.

    Args:
        basepath: A pathlib.Path-like object or str pointing to the
            base path where a log file is stored.
        docset_id: The unique ID str for the document set used in the
            tests that created this log file.
        config_id: The unique ID str for the configuration used in the
            tests that created this log file.
    """
    return Path(basepath) / f'{docset_id}--{config_id}-log.json'


class BenchmarkLog:
    """Class for logging and managing stats from benchmark tests.

    An instance of this class encapsulates all the details about a
    benchmark test run: the document set and configuration that were
    tested, the stats collected during indexing, and stats collected
    during search tests. It allows you to save stats to disk for
    retrieval later, and there is a factory method for instantiating a
    BenchmarkLog from data that was saved to disk. It also allows you
    to generate a report from the logged stats (returned as a
    dictionary but suitable for writing out in tabular form).

    Each stats set (indexing and searching) is merely a dictionary
    attached to the log object; currently the structure is not
    enforced by this class, although the `compile_report` method does
    expect a specific structure -- the structure that BenchmarkRunner
    creates when tests are run. A future TODO would be to formalize
    the stats structures to facilitate creating alternative
    BenchmarkRunner-like classes. They are documented below, under the
    appropriate class attributes.

    Attributes:
        docset_id: The unique ID str for the document set used in the
            tests that created this log instance.
        configdata: The ConfigData or ConfigData-like object storing
            configuration info for the tests that created this log
            instance.
        indexing_stats: A dictionary containing stats from the
            'indexing' portion of a benchmark test run. If indexing
            tests have not yet been run, this is an empty dict. Else,
            the expected structure is, e.g., given a 10,000 document
            DocSet:
                {
                    'batch_size': 1000,
                    'indexing_total_secs': 102.3,
                    'indexing_average_secs': 10.23,
                    'commit_total_secs': 50.12,
                    'commit_average_secs': 5.012,
                    'total_secs': 152.42,
                    'average_secs': 15.242
                }
        search_stats: A dictionary containing stats from the 'search'
            portion of a benchmark test run. If search tests have not
            yet been run, this is an empty dict. Else, the expected
            structure is, e.g.:
                {
                    'First search set label': {
                        'term_results': [
                            {'term': '',
                             'hits': 200,
                             'qtime_ms': 1592},
                            {'term': 'test term 1',
                             'hits': 50,
                             'qtime_ms': 433},
                            {'term': 'test term 2',
                             'hits': 36,
                             'qtime_ms': 290},
                        ],
                        'avg_qtime_ms': 771.6667,
                        'total_qtime_ms': 2315
                    },
                    'Second search set label': {
                        'term_results': [
                            {'term': '',
                             'hits': 200,
                             'qtime_ms': 698},
                            {'term': 'test term 1',
                             'hits': 50,
                             'qtime_ms': 101},
                            {'term': 'test term 2',
                             'hits': 36,
                             'qtime_ms': 95},
                        ],
                        'avg_qtime_ms': 298.0,
                        'total_qtime_ms': 894
                    }
                }
            Each top-level dictionary key is a label containing a
            description or specification for a search test, where
            several terms are searched using the same settings (such as
            a specific 'fq') and timings are recorded.
        filepath: A pathlib.Path object with the full path to the file
            containing stats for this BenchmarkLog, or None if that
            file has not yet been created.
        config_id: The `config_id` attribute of the `configdata`
            object.
    """

    def __init__(self, docset_id: str, configdata: ConfigDataLike) -> None:
        """Inits a BenchmarkLog instance.

        Args:
            docset_id: See `docset_id` attribute.
            configdata: See `configdata` attribute.
        """
        self.docset_id = docset_id
        self.configdata = configdata
        self.indexing_stats: Stats = {}
        self.search_stats: SearchStats = {}
        self._filepath: Optional[Path] = None

    @property
    def filepath(self) -> Optional[Path]:
        """The full path to the file with saved stats.

        See the `filepath` attribute.
        """
        return self._filepath

    @property
    def config_id(self) -> str:
        """Ihe ID str from the `configdata` object.

        See the `config_id` attribute.
        """
        return self.configdata.config_id

    def save_to_json_file(self, filepath: PathLike) -> Path:
        """Saves the current state to a file as JSON data.

        Args:
            filepath: A pathlib.Path-like or str that points to the
                full path for the save file (including the filname).

        Returns:
            The filepath as a pathlib.Path object.
        """
        self._filepath = Path(filepath)
        json_str = ujson.dumps({
            'docset_id': self.docset_id,
            'configdata': asdict(self.configdata),
            'indexing_stats': self.indexing_stats,
            'search_stats': self.search_stats
        })
        with open(self._filepath, 'w') as json_fh:
            json_fh.write(json_str)
        return self._filepath

    @classmethod
    def load_from_json_file(cls: Type[B],
                            filepath: PathLike,
                            cd_cls: Type[ConfigDataLike] = ConfigData) -> B:
        """Creates a new BenchmarkLog from data saved to disk.

        Args:
            filepath: A pathlib.Path-like or str pointing to the full
                path for the save file to load (including filename).
            cd_cls: (Optional.) The class to use when recreating the
                `configdata` attribute. By default, this is ConfigData,
                but it can be a subclass or any ConfigDataLike type
                that stores your configuration data.
        """
        with open(filepath) as f:
            json_str = f.read()
        data = ujson.loads(json_str)
        configdata = cd_cls(**data['configdata'])
        bmark_log = cls(data['docset_id'], configdata)
        bmark_log.indexing_stats = data['indexing_stats']
        bmark_log.search_stats = data['search_stats']
        bmark_log._filepath = Path(filepath)
        return bmark_log

    def compile_report(self,
                       aggregate_search_groups: Dict[str, Sequence[str]] = {}
                       ) -> BenchmarkLogReport:
        """Generate a report (dictionary) for the current stats.

        The report contains average timings for each test, grouped by
        test types and subtypes.

        For search tests, an average for each individual test set is
        included plus each aggregate grouping. When terms lists include
        a blank term (i.e., ''), the result for the blank search is
        pulled into its own category.

        Args:
            aggregate_search_groups: A dictionary that specifies any
                aggregate groupings you want to create based on search
                stats in the report. It should be formatted as follows:
                    {
                        'Group 1 label': [
                            'First search set label',
                            'Fourth search set label',
                            'Sixth search set label'
                        ],
                        'Group 2 label': [
                            'Second search set label',
                            'Third search set label',
                            'Fifth search set label'
                        ]
                    }
                Dictionary keys are group labels. These will become
                new SEARCH groups in the report. Values are sequences
                of the search test labels that belong in that group.
                (Search test labels are the top-level keys in the
                `search_stats` attribute.) To create the aggregate
                group, results from each individual search set are
                combined and then averaged.

        Returns:
            A dictionary containing the report data. This includes the
            total and/or average timings for each test, organized by
            type. Timings are expressed as (number, str) tuples, where
            the string indicates the time unit: (1.0, 's') is 1 second,
            and (1000, 'ms') is 1000 milliseconds.

            A full report data dictionary might look something like:
                {
                    'ADD': {
                        # These are timings for adding documents to
                        # Solr (apart from committing).
                        'total': (102.1, 's'),
                        'avg per 1000 docs': (10.21, 's')
                    },
                    'COMMIT': {
                        # These timings are just for committing docs to
                        # Solr.
                        'total': (50.12, 's'),
                        'avg per 1000 docs': (5.012, 's'),
                    },
                    'INDEXING': {
                        # These timings are for combined add + commit.
                        'total': (152.22, 's'),
                        'avg per 1000 docs': (15.222, 's')
                    },
                    'SEARCH': {
                        # For search tests, the same sets and groups
                        # appear under BLANK and ALL TERMS. The former
                        # includes only timings for empty searches, and
                        # the latter includes timings for all terms
                        # (including the empty searches).
                        'BLANK': {
                            '2-letter terms - No Facets': (52, 'ms'),
                            '2-letter terms - All Facets': (184, 'ms'),
                            '3-letter terms - No Facets': (58, 'ms'),
                            '3-letter terms - All Facets': (268, 'ms'),
                            '4-letter terms - No Facets': (92, 'ms'),
                            '4-letter terms - All Facets': (262, 'ms'),
                            # Below this are all aggregate groupings.
                            '2-letter terms': (118, 'ms'),
                            '3-letter terms': (163, 'ms'),
                            '4-letter terms': (177, 'ms'),
                            'No Facets': (67.3333, 'ms'),
                            'All Facets': (238, 'ms'),
                            'Overall': (152.6667, 'ms')
                        },
                        'ALL TERMS': {
                            '2-letter terms - No Facets': (30, 'ms'),
                            '2-letter terms - All Facets': (86, 'ms'),
                            '3-letter terms - No Facets': (55, 'ms'),
                            '3-letter terms - All Facets': (125, 'ms'),
                            '4-letter terms - No Facets': (60, 'ms'),
                            '4-letter terms - All Facets': (199, 'ms'),
                            # Below this are all aggregate groupings.
                            '2-letter terms': (58, 'ms'),
                            '3-letter terms': (90, 'ms'),
                            '4-letter terms': (129.5, 'ms'),
                            'No Facets': (48.3333, 'ms'),
                            'All Facets': (136.6667, 'ms'),
                            'Overall': (92.5, 'ms')
                        }
                    }
                }
        """
        i_stats = self.indexing_stats
        s_stats = self.search_stats
        i_avg_label = f"avg per {i_stats['batch_size']} docs"
        data: BenchmarkLogReport = {
            'ADD': {
                'total': (i_stats.get('indexing_total_secs', 0), 's'),
                i_avg_label: (i_stats.get('indexing_average_secs', 0), 's')
            },
            'COMMIT': {
                'total': (i_stats.get('commit_total_secs', 0), 's'),
                i_avg_label: (i_stats.get('commit_average_secs', 0), 's')
            },
            'INDEXING': {
                'total': (i_stats.get('total_secs', 0), 's'),
                i_avg_label: (i_stats.get('average_secs', 0), 's')
            },
            'SEARCH': {
                'BLANK': {},
                'ALL TERMS': {}
            }
        }

        for label, details in s_stats.items():
            term_results = details['term_results']
            blanks = (tr for tr in term_results if tr['term'] == '')
            blank = next(blanks, None)
            if blank:
                blank_qtime = blank['qtime_ms']
                data['SEARCH']['BLANK'][label] = (blank_qtime, 'ms')
            allterms_qtime = details['avg_qtime_ms']
            data['SEARCH']['ALL TERMS'][label] = (allterms_qtime, 'ms')

        for grp_label, labels in aggregate_search_groups.items():
            blank_tally = []
            search_tally = []
            for label in labels:
                details = s_stats[label]
                term_results = details['term_results']
                blanks = (tr for tr in term_results if tr['term'] == '')
                blank = next(blanks, None)
                if blank:
                    blank_tally.append(blank['qtime_ms'])
                search_tally.extend(
                    [tr['qtime_ms'] for tr in details['term_results']]
                )
            if blank_tally:
                grp_blank_qt = round(sum(blank_tally) / len(blank_tally), 4)
                data['SEARCH']['BLANK'][grp_label] = (grp_blank_qt, 'ms')
            grp_allterms_qt = round(sum(search_tally) / len(search_tally), 4)
            data['SEARCH']['ALL TERMS'][grp_label] = (grp_allterms_qt, 'ms')
        return data


def _scrape_qtime(solr_response: str) -> float:
    """Returns the query time (in seconds!) from a Solr response str."""
    pattern = r'QTime\D+(\d+)'
    qt_match = re.search(pattern, solr_response)
    try:
        qtime = qt_match.group(1)  # type: ignore[union-attr]
    except AttributeError:
        raise ValueError(
            f"Cannot scrape query time from Solr response string. Looking "
            f"for pattern r'{pattern}' in: {solr_response}."
        )
    return int(qtime) * 0.001


def _compile_timings(timings: RawEventTimings) -> CompiledEventTimingsInfo:
    """Compiles timings from a sequence of raw (event, timing) tuples."""
    stats: CompiledEventTimingsInfo = {
        'timings': {},
        'totals': {},
        'averages': {}
    }
    default_time = 0
    for event, time in timings:
        stats['timings'][event] = stats['timings'].get(event, []) + [time]
        total = stats['totals'].get(event, default_time) + time
        stats['totals'][event] = round(total, 6)
    for event, event_timings in stats['timings'].items():
        avg = stats['totals'][event] / len(event_timings)
        stats['averages'][event] = round(avg, 6)
    return stats


def _compile_indexing_results(raw_timings: RawEventTimings,
                              ndocs: int,
                              batch_size: int) -> StatsWithTimings:
    """Compiles stats from a sequence of indexing timings."""
    tstats = _compile_timings(raw_timings)
    timings = tstats['timings']
    totals = tstats['totals']
    avgs = tstats['averages']
    nbatches = len(timings['indexing'])
    return {
        'batch_size': batch_size,
        'total_docs': ndocs,
        'indexing_timings_secs': timings['indexing'],
        'indexing_total_secs': totals['indexing'],
        'indexing_average_secs': avgs['indexing'],
        'commit_timings_secs': timings['committing'],
        'commit_total_secs': totals['committing'],
        'commit_average_secs': avgs['committing'],
        'total_secs': totals['indexing'] + totals['committing'],
        'average_secs': (totals['indexing'] + totals['committing']) / nbatches
    }


def _compile_search_results(term_results: List[TermResult]) -> SearchSetResult:
    """Compiles qtime averages from qtimes in term results."""
    qtime = sum([r['qtime_ms'] for r in term_results])
    return {
        'total_qtime_ms': round(qtime, 4),
        'avg_qtime_ms': round(qtime / len(term_results), 4),
        'term_results': term_results,
    }


class RunnerConfigurationError(Exception):
    """Raised when a BenchmarkRunner is not properly configured."""


class BenchmarkRunner:
    """Class for running Solr benchmark tests.

    One BenchmarkRunner instance is designed to be able to run multiple
    tests (with multiple configurations), although you can of course
    instantiate a new runner for each test.

    To use:
    - Instantiate by passing a pysolr.Solr-like object to __init__ that
      will act on your test Solr instance and test core or collection.
    - Configure a new test run by passing a document set ID and
      ConfigData instance to the `configure` method. OR if you are
      continuing a past test run, load data from a saved log via the
      `configure_from_saved_log` method.
    - Run indexing tests by calling the `index_docs` method. Stats are
      saved to the `log` BenchmarkLog object. Note that running
      indexing tests again will overwrite the previous results.
    - Run search tests.
        - You probably want multiple sets of search tests, where each
          entails running through the same set of terms while changing
          other search settings, such as including facet details or
          using an 'fq' parameter to limit the search.
        - For each test set, call `run_searches`. Provide your list of
          search terms, a label for this test set, query arguments, and
          other search parameters.
        - Stats are saved to the `log` BenchmarkLog object as tests are
          run.
        - The provided label is used as the key for storing results, so
          calling `run_searches` a second time using the same label
          will overwrite the results for that one test set (and only
          that one test set).
    - Optionally, save the test results for later via the `save_log`
      method.
    - Compile a report for this test by calling `log.compile_report`.
      Format the report for output based on your needs. (See the
      `BenchmarkLog.compile_report` method for information about the
      returned report format.)

    Attributes:
        conn: An object encapsulating a pysolr-like API for interacting
            with the Solr instance under test.
        log: The BenchmarkLog object that handles tracking stats for
            this runner's tests. This is None unless the `configure` or
            `configure_from_save_log` methods have been called.
        log_basepath: A pathlib.Path object representing the base path
            where the saved file for the `log` object lives. This is
            None until a value can be determined -- either by loading
            an existing file via the `configure_from_saved_log` method
            or by saving a file and providing a basepath via the
            `save_log` method.
        is_configured: True if the `configure` or
            `configure_from_saved_log` methods have been called. (Tests
            cannot be run until the BenchmarkRunner is configured.)
        logpath: A pathlib.Path object representing the full path to
            the saved BenchmarkLog file. This is None unless the
            `configure_from_saved_log` or `save_log` methods have been
            called.
    """

    def __init__(self, conn: PysolrConnLike):
        """Inits a BenchmarkRunner instance.

        Args:
            conn: See the `conn` attribute.
        """
        self.conn = conn
        self.log: Optional[BenchmarkLog] = None
        self.log_basepath: Optional[Path] = None

    def configure(self: R, docset_id: str, configdata: ConfigDataLike) -> R:
        """Assigns new config data for the next run of tests.

        This is one of two methods you can use to configure a new
        BenchmarkRunner instance (the other is
        `configure_from_saved_log`). Note that you must configure each
        new BenchmarkRunner instance before running tests.

        You may change configuration for a new run of tests by calling
        this method again with a different configuration.

        Args:
            docset_id: The unique ID str for the document set you'll
                use in the next test run.
            configdata: The ConfigData or ConfigData-like object
                storing Solr config info for the next test run.

        Returns:
            This BenchmarkRunner instance.
        """
        self.log = BenchmarkLog(docset_id, configdata)
        return self

    def configure_from_saved_log(self: R, log_path: PathLike) -> R:
        """Assigns config data from a saved BenchmarkLog.

        This is one of two methods you can use to configure a new
        BenchmarkRunner instance (the other is `configure`). Note that
        you must configure each new BenchmarkRunner instance before
        running tests.

        You may also change configuration for a new run of tests by
        calling this method again with a different log file.

        Args:
            log_path: A pathlib.Path-like or str referencing the full
                path to the save file for a BenchmarkLog that you wish
                to load. The base path for this file is saved to the
                `log_basepath` attribute -- so if you wish to save the
                log file again, you do not need to supply it.

        Returns:
            This BenchmarkRunner instance.
        """
        log_path = Path(log_path)
        self.log = BenchmarkLog.load_from_json_file(log_path)
        self.log_basepath = log_path.parent
        return self

    @property
    def is_configured(self) -> bool:
        """True if this has been configured.

        See the `is_configured` attribute.
        """
        return bool(self.log)

    @property
    def logpath(self) -> Optional[Path]:
        """The full path (a pathlib.Path) of the saved `log` file.

        This is None if there is either no `log` yet associated with
        this object (because it has not yet been configured) or if
        there is not yet a save-file associated with the log (because
        tests have not been run and/or it has not yet been saved).

        See the `log_path` attribute.
        """
        try:
            return compose_log_json_filepath(
                self.log_basepath,    # type: ignore[arg-type]
                self.log.docset_id,   # type: ignore[union-attr]
                self.log.config_id    # type: ignore[union-attr]
            )
        except (TypeError, AttributeError):
            return None

    def save_log(self, basepath: Optional[PathLike] = None) -> Path:
        """Saves the `log` to disk.

        Args:
            basepath: (Optional.) A pathlib.Path-like or str that
                references the location where you want to save the file
                for the `log` object. The provided path is saved to the
                `log_basepath` attribute so that this argument becomes
                optional on subsequent calls to `save_log`. (If you do
                not supply this argument and `log_basepath` is empty,
                an error will be raised.)

        Returns:
            A pathlib.Path object referencing the full path of the
                saved file.
        """
        self.log_basepath = Path(basepath) if basepath else self.log_basepath
        try:
            return self.log.save_to_json_file(  # type: ignore[union-attr]
                self.logpath                    # type: ignore[arg-type]
            )
        except (TypeError, AttributeError, FileNotFoundError):
            raise ValueError(
                f"Attempted to save log data to `{self.logpath}`, an invalid "
                f"path. Please provide a valid directory for the 'basepath' "
                f"argument."
            ) from None

    def index_docs(self,
                   docset: DocSet,
                   batch_size: int = 1000,
                   verbose: bool = True) -> StatsWithTimings:
        """Runs indexing tests against the provided DocSet.

        Timings for adding documents to the index and committing them
        are kept separate, although bear in mind that your autoCommit
        settings in Solr may trigger commits during an add operation,
        which here would count as part of the 'add' timings.

        Documents are added in batches, controlled by the `batch_size`
        argument. Each batch is followed by a hard commit. E.g., with a
        DocSet containing 100000 documents and a batch size of 1000, it
        would index 100 batches of 1000 documents each.

        Docs are left indexed so that you can run search tests against
        the document set immediately following indexing tests.

        Stats that are returned are also saved to
        self.log.indexing_stats. But, if you run `index_docs` multiple
        times, the new stats overwrite the previous ones.

        Args:
            docset: The DocSet object containing documents to index.
            batch_size: (Optional.) The number of documents to include
                in each batch. Default is 1000.
            verbose: (Optional.) If True, brief status messages
                indicating what documents are being indexed will be
                printed to stdout as the tests run. Default is True.

        Returns:
            A dict containing the stats from this indexing test run,
            such as the following.
                {
                    'batch_size': 1000,
                    'indexing_total_secs': 102.3,
                    'indexing_average_secs': 10.23,
                    'commit_total_secs': 50.12,
                    'commit_average_secs': 5.012,
                    'total_secs': 152.42,
                    'average_secs': 15.242
                }
        """
        def _do(batch: List[Dict[str, Any]], i: int) -> RawEventTimings:
            timings: RawEventTimings = []
            if verbose:
                print(f'Indexing {i + 1 - batch_size} to {i}.')
            index_response = self.conn.add(batch, commit=False)
            index_qtime = _scrape_qtime(index_response)
            timings.append(('indexing', index_qtime))
            if verbose:
                print('Committing...')
            commit_response = self.conn.commit()
            commit_qtime = _scrape_qtime(commit_response)
            timings.append(('committing', commit_qtime))
            return timings

        if not self.is_configured:
            raise RunnerConfigurationError(
                'Attempted to run tests without adding configuration data via '
                '`configure` or `configure_from_saved_log` methods.'
            )

        # This next line is a little redundant, but it makes it simpler
        # to ignore mypy errors that occur because self.log is defined
        # elsewhere as potentially being None. In reality, the previous
        # check for `self.is_configured` ensures self.log is not None
        # when we get to this point.
        log_docset_id = self.log.docset_id  # type: ignore[union-attr]
        if log_docset_id != docset.id:
            raise RunnerConfigurationError(
                f"The 'id' of the given docset (`{docset.id}`) does not match "
                f"the configured 'docset_id' (`{log_docset_id}`)."
            )

        timings: RawEventTimings = []
        batch: List[Dict[str, Any]] = []
        for i, doc in enumerate(docset.docs):
            if verbose and i % batch_size == 0:
                print('Gathering docs.')
            batch.append(doc)
            if (i + 1) % batch_size == 0:
                timings.extend(_do(batch, i))
                batch = []
        if batch:
            timings.extend(_do(batch, i))

        total = docset.total_docs
        stats = _compile_indexing_results(timings, total, batch_size)
        self.log.indexing_stats = stats  # type: ignore[union-attr]
        return stats

    def search(self,
               q: str,
               kwargs: Mapping[str, Any],
               rep_n: int = 1,
               ignore_n: int = 0,
               blank_q: str = '') -> SearchResult:
        """Fires one Solr search test and returns the result.

        Args:
            q: The query string, aka the 'q' parameter passed to Solr.
            kwargs: A dict containing any other query parameters to
                send to Solr for this test.
            rep_n: (Optional.) Fire the search this many times and
                average the query times. Default is 1. (0 will skip the
                search altogether.)
            ignore_n: (Optional.) Ignore the first N search repetitions
                when averaging the query times. This can be useful if
                you only want to measure timings for cached queries and
                ignore cold ones. Default is 0.
            blank_q: (Optional.) If you're using "blank" queries in
                your tests to return all results, then you may need a
                substitute value to use for `q` if an empty string
                won't do it, depending on how your search handler is
                set up. For instance, you may need to use '*:*'
                instead. Default is an empty string.

        Returns:
            A dict with the following structure.
            - 'result': The result object from whatever Solr interface
              you're using (such as, pysolr.Result). If `rep_n` >1,
              it will be the result from the last repetition.
            - 'hits': The number of hits the query produced.
            - 'qtime_ms': The query time, in milliseconds. This is the
              average of the qtime for all repetitions, excluding the
              first `ignore_n` repetitions.
        """
        q = q or blank_q
        timings: RawEventTimings = []
        hits = 0
        for i in range(rep_n):
            if i < ignore_n:
                result = self.conn.search(q=q, **kwargs)
            else:
                result = self.conn.search(q=q, **kwargs)
                hits = hits or result.hits
                timings.append(('search', result.qtime))
        tstats = _compile_timings(timings)
        # The canonical query time for this search is the average of
        # the repetitions, excluding the ones we ignored.
        qtime_ms = round(tstats['averages'].get('search', 0), 4)
        return {
            'result': result,
            'hits': hits,
            'qtime_ms': qtime_ms
        }

    def run_searches(self,
                     terms: Sequence[str],
                     label: str,
                     query_kwargs: Optional[Mapping[str, Any]] = None,
                     rep_n: int = 0,
                     ignore_n: int = 0,
                     blank_q: str = '',
                     verbose: bool = True) -> SearchSetResult:
        """Runs one set of test searches.

        Running a "set of test searches" comprises querying Solr for
        each in a predefined list of terms, using the same query
        settings for each, and recording the query timings for each.

        (For different sets of test searches, you might vary the sets
        of terms or change specific query settings. The key would be to
        isolate certain features to measure how much they change with
        different Solr configurations.)

        Returned stats are also saved to self.log.search_stats, using
        the provided label as a key. Running different sets of search
        tests (with different labels) saves stats for each to a
        different key. Repeating the same label will overwrite stats
        for that key.

        Args:
            terms: A sequence containing search terms to test.
            label: A meaningful label for this test set.
            query_kwargs: (Optional.) A dict containing static
                parameters to send to Solr with each query. Default is
                an empty dict.
            rep_n: (Optional.) For each term, it will fire the search
                this many times and average the query times. Default is
                1. (0 will skip the search altogether.)
            ignore_n: (Optional.) Ignore the first N search repetitions
                when averaging the query times. This can be useful if
                you only want to measure timings for cached queries and
                ignore cold ones. Default is 0.
            blank_q: (Optional.) If you're using "blank" queries in
                your tests as a way to return all results, then you may
                need a substitute value to use for 'q' if an empty
                string won't do it, depending on how your search
                handler is set up. For instance, you may need to use
                '*:*' instead. Default is an empty string.
            verbose: (Optional.) If True, status messages showing test
                progress are printed to stdout. Default is True.

        Returns:
            A dict containing the stats from this search test run, such
            as the following.
                {
                    'term_results': [
                        {'term': '',
                         'hits': 200,
                         'qtime_ms': 1592},
                        {'term': 'test term 1',
                         'hits': 50,
                         'qtime_ms': 433},
                        {'term': 'test term 2',
                         'hits': 36,
                         'qtime_ms': 290},
                    ],
                    'avg_qtime_ms': 771.6667,
                    'total_qtime_ms': 2315
                }
        """
        if not self.is_configured:
            raise RunnerConfigurationError(
                'Attempted to run tests without adding configuration data via '
                '`configure` or `configure_from_saved_log` methods.'
            )
        if verbose:
            print(f'{label} ({len(terms)} searches) ', end='', flush=True)
        term_results: List[TermResult] = []
        for term in terms:
            result = self.search(term, query_kwargs or {}, rep_n, ignore_n)
            term_results.append({
                'term': term,
                'hits': result['hits'],
                'qtime_ms': result['qtime_ms']
            })
            if verbose:
                print('.', end='', flush=True)
        if verbose:
            print(flush=True)
        stats = _compile_search_results(term_results)
        self.log.search_stats[label] = stats  # type: ignore[union-attr]
        return stats
