"""Contains classes for running benchmarking tests and compiling stats."""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import re
from typing import Optional

import ujson


@dataclass
class ConfigData:
    """Class for storing info about a configuration under test."""

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

    def derive(self, config_id, **kwargs):
        """Base a new ConfigData object on this object.

        Values are copied to the new object unless overridden in a
        kwarg. The only required new value is a new config_id.
        """
        new_obj = replace(self)
        new_obj.config_id = config_id
        for arg, val in kwargs.items():
            setattr(new_obj, arg, val)
        return new_obj


def compose_log_json_filepath(basepath, docset_id, config_id):
    """Get the filepath for a log file from a docset & config id."""
    return Path(basepath) / f'{docset_id}--{config_id}-log.json'


class BenchmarkLog:
    """Class for tracking and compiling benchmarking stats."""

    def __init__(self, docset_id, configdata):
        self.docset_id = docset_id
        self.configdata = configdata
        self.indexing_stats = {}
        self.search_stats = {}
        self._filepath = None

    @property
    def filepath(self):
        return self._filepath

    @property
    def config_id(self):
        return self.configdata.config_id

    def save_to_json_file(self, filepath):
        self._filepath = filepath
        json_str = ujson.dumps({
            'docset_id': self.docset_id,
            'configdata': asdict(self.configdata),
            'indexing_stats': self.indexing_stats,
            'search_stats': self.search_stats
        })
        with open(filepath, 'w') as json_fh:
            json_fh.write(json_str)
        return filepath

    @classmethod
    def load_from_json_file(cls, filepath, cfgdata_cls=ConfigData):
        with open(filepath) as f:
            json_str = f.read()
        data = ujson.loads(json_str)
        configdata = cfgdata_cls(**data['configdata'])
        bmark_log = cls(data['docset_id'], configdata)
        bmark_log.indexing_stats = data['indexing_stats']
        bmark_log.search_stats = data['search_stats']
        bmark_log._filepath = filepath
        return bmark_log

    def compile_report(self, aggregate_search_groups={}):
        i_stats = self.indexing_stats
        s_stats = self.search_stats
        i_avg_label = f"avg per {i_stats['batch_size']} docs"
        data = {
            'ADD': {
                'total': (i_stats.get('indexing_total_secs'), 's'),
                i_avg_label: (i_stats.get('indexing_average_secs'), 's')
            },
            'COMMIT': {
                'total': (i_stats.get('commit_total_secs'), 's'),
                i_avg_label: (i_stats.get('commit_average_secs'), 's')
            },
            'INDEXING': {
                'total': (i_stats.get('total_secs'), 's'),
                i_avg_label: (i_stats.get('average_secs'), 's')
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


def _scrape_qtime(solr_response):
    try:
        qtime = re.search(r'QTime\D+(\d+)', solr_response).group(1)
    except AttributeError:
        return
    return int(qtime) * 0.001


def _compile_timings_stats(timings):
    stats = {'timings': {}, 'totals': {}, 'averages': {}}
    default_time = 0
    for event, time in timings:
        stats['timings'][event] = stats['timings'].get(event, []) + [time]
        total = stats['totals'].get(event, default_time) + time
        stats['totals'][event] = round(total, 6)
    for event, event_timings in stats['timings'].items():
        avg = stats['totals'][event] / len(event_timings)
        stats['averages'][event] = round(avg, 6)
    return stats


def _compile_indexing_results(timings, ndocs, batch_size):
    tstats = _compile_timings_stats(timings)
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


def _compile_search_results(term_results):
    qtime = sum([r['qtime_ms'] for r in term_results])
    return {
        'total_qtime_ms': round(qtime, 4),
        'avg_qtime_ms': round(qtime / len(term_results), 4),
        'term_results': term_results,
    }


class RunnerConfigurationError(Exception):
    pass


class BenchmarkRunner:
    """Class for running Solr benchmark tests."""

    def __init__(self, conn):
        self.conn = conn
        self.log = None
        self.log_basepath = None

    def configure(self, docset_id, configdata):
        self.log = BenchmarkLog(docset_id, configdata)
        return self

    def configure_from_saved_log(self, log_path):
        log_path = Path(log_path)
        self.log = BenchmarkLog.load_from_json_file(log_path)
        self.log_basepath = log_path.parent
        return self

    @property
    def is_configured(self):
        return bool(self.log)

    @property
    def logpath(self):
        try:
            return compose_log_json_filepath(
                self.log_basepath, self.log.docset_id, self.log.config_id
            )
        except TypeError:
            return None

    def save_log(self, basepath=None):
        self.log_basepath = basepath or self.log_basepath
        try:
            return self.log.save_to_json_file(self.logpath)
        except (TypeError, FileNotFoundError):
            raise ValueError(
                f"Attempted to save log data to `{self.logpath}`, an invalid "
                f"path. Please provide a valid directory for the 'basepath' "
                f"argument."
            ) from None

    def index_docs(self, docset, batch_size=1000, verbose=True):
        def _do(batch, i):
            timings = []
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

        if self.log.docset_id != docset.id:
            raise RunnerConfigurationError(
                f"The 'id' of the given docset (`{docset.id}`) does not match "
                f"the configured 'docset_id' (`{self.log.docset_id}`)."
            )

        timings = []
        batch = []
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
        self.log.indexing_stats = stats
        return stats

    def search(self, q, kwargs, rep_n=1, ignore_n=0, blank_q=''):
        q = q or blank_q
        timings = []
        hits = None
        for i in range(rep_n):
            if i < ignore_n:
                result = self.conn.search(q=q, **kwargs)
            else:
                result = self.conn.search(q=q, **kwargs)
                hits = hits or result.hits
                timings.append(('search', result.qtime))
        tstats = _compile_timings_stats(timings)
        # The canonical query time for this search is the average of
        # the repetitions, excluding the ones we ignored.
        qtime_ms = round(tstats['averages'].get('search', 0), 4)
        return {
            'result': result,
            'hits': hits,
            'qtime_ms': qtime_ms
        }

    def run_searches(self, terms, label, query_kwargs=None, rep_n=0,
                     ignore_n=0, blank_q='', verbose=True):
        if not self.is_configured:
            raise RunnerConfigurationError(
                'Attempted to run tests without adding configuration data via '
                '`configure` or `configure_from_saved_log` methods.'
            )
        if verbose:
            print(f'{label} ({len(terms)} searches) ', end='', flush=True)
        term_results = []
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
        self.log.search_stats[label] = stats
        return stats
