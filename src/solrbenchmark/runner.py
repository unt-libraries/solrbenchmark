"""Contains classes for running benchmarking tests and compiling stats."""
import itertools

import ujson

from . import timer


class BenchmarkTestLog(object):
    """Class for tracking and compiling benchmarking stats."""

    def __init__(self, test_id, solr_version=None, solr_caches=None,
                 solr_conf=None, solr_schema=None, os=None, os_memory=None,
                 jvm_memory=None, jvm_settings=None, collection_size=None,
                 notes=None):
        self.test_id = test_id
        self.metadata = {
            'solr_version': solr_version,
            'solr_caches': solr_caches,
            'solr_conf': solr_conf,
            'solr_schema': solr_schema,
            'os': os,
            'os_memory': os_memory,
            'jvm_memory': jvm_memory,
            'jvm_settings': jvm_settings,
            'collection_size': collection_size,
            'notes': notes
        }
        self.reset()

    def reset(self):
        self.indexing_stats = {}
        self.search_stats = {}

    def save_to_json_file(self, filepath):
        json_str = ujson.dumps({
            'metadata': self.metadata,
            'indexing_stats': self.indexing_stats,
            'search_stats': self.search_stats
        })
        with open(filepath, 'w') as f:
            f.write(json_str)

    @classmethod
    def load_from_json_file(cls, filepath):
        with open(filepath) as f:
            json_str = f.read()
        data = ujson.loads(json_str)
        test_log = cls(data['test_id'], **data['metadata'])
        test_log.indexing_stats = data['indexing_stats']
        test_log.search_stats = data['search_stats']
        return test_log

    def compile_report(self, aggregate_groups):
        i_stats = self.indexing_stats
        s_stats = self.search_stats
        unit = 'avg secs per {} docs'.format(i_stats['batch_size'])
        data = {
            'ADD total secs': i_stats.get('indexing_total_secs'),
            'ADD {}'.format(unit): i_stats.get('indexing_average_secs'),
            'COMMIT total secs': i_stats.get('commit_total_secs'),
            'COMMIT {}'.format(unit): i_stats.get('commit_average_secs'),
            'INDEXING total secs': i_stats.get('total_secs'),
            'INDEXING {}'.format(unit): i_stats.get('average_secs')
        }

        for label, details in s_stats.items():
            if details['blank_included']:
                key = 'SEARCH - BLANK - {} - avg ms'.format(label)
                data[key] = details['term_results'][0]['qtime_ms']
            data['SEARCH - {} - avg ms'.format(label)] = details['avg_qtime_ms']

        for group_label, labels in aggregate_groups.items():
            blank_tally = []
            search_tally = []
            for label in labels:
                details = s_stats[label]
                if details['blank_included']:
                    blank_tally.append(details['term_results'][0]['qtime_ms'])
                search_tally.extend(
                    [tr['qtime_ms'] for tr in details['term_results']]
                )
            if blank_tally:
                key = 'SEARCH BLANK - {} - avg ms'.format(group_label)
                data[key] = round(sum(blank_tally) / len(blank_tally), 4)
            key = 'SEARCH - {} - avg ms'.format(group_label)
            data[key] = round(sum(search_tally) / len(search_tally), 4)
        return data


class BenchmarkTestRunner(object):
    """Class for running Solr benchmark tests."""

    def __init__(self, test_docset, test_log, conn):
        self.test_docset = test_docset
        self.test_log = test_log
        self.conn = conn

    def index_docs(self, batch_size=1000, verbose=True, track_commits=True,
                   index_timer=None):
        index_timer = index_timer or timer.Timer()
        i = 1
        while True:
            batch = list(itertools.islice(self.test_docset.docs, batch_size))
            if batch:
                if verbose:
                    print(f'Indexing {i} to {i + batch_size - 1}.')
                index_timer.start('indexing')
                self.conn.add(batch, commit=False)
                index_timer.end('indexing')
                if verbose:
                    print('Committing...')
                if track_commits:
                    index_timer.start('committing')
                    self.conn.commit()
                    index_timer.end('committing')
                else:
                    self.conn.commit()
                i += batch_size
            else:
                break
        total = self.test_docset.total_docs
        stats = self.compile_indexing_results(index_timer, total, batch_size)
        self.test_log.indexing_stats = stats
        return stats

    def compile_indexing_results(self, index_timer, ndocs, batch_size):
        tstats = index_timer.compile_statistics(convert_to_seconds=True)
        timings = tstats['event_timings']
        totals = tstats['event_totals']
        avgs = tstats['event_averages']
        indexing_stats = {
            'batch_size': batch_size,
            'total_docs': ndocs,
            'indexing_timings_secs': timings['indexing'],
            'indexing_total_secs': totals['indexing'],
            'indexing_average_secs': avgs['indexing'],
            'total_secs': totals['indexing'],
            'average_secs': avgs['indexing']
        }
        if 'committing' in timings:
            nb = len(timings['indexing'])
            avg = ((avgs['indexing'] * nb) + (avgs['committing'] * nb)) / nb
            total = totals['indexing'] + totals['committing']
            indexing_stats.update({
                'commit_timings_secs': timings['committing'],
                'commit_total_secs': totals['committing'],
                'commit_average_secs': avgs['committing'],
                'total_secs': index_timer.round(total),
                'average_secs': index_timer.round(avg)
            })
        return indexing_stats

    def search(self, q, kwargs, repeat_n=0, ignore_n=0):
        search_timer = timer.Timer()
        hits = None
        for i in range(0, repeat_n + 1):
            if i < ignore_n:
                self.conn.search(q=q, **kwargs)
            else:
                search_timer.start('search')
                result = self.conn.search(q=q, **kwargs)
                search_timer.end('search')
                hits = hits or result.hits
        tstats = search_timer.compile_statistics(convert_to_seconds=True)
        return {
            'hits': hits,
            'avg_qtime_ms': round(tstats['event_averages']['search'] * 1000, 4)
        }

    def run_searches(self, terms, label, query_kwargs, repeat_n=0, ignore_n=0,
                     verbose=True):
        if verbose:
            print(f"{label} ({len(terms)} searches) ", end='', flush=True)
        term_results = []
        for term in terms:
            result = self.search(term, kwargs, repeat_n, ignore_n)
            term_results.append({
                'term': term,
                'hits': result['hits'],
                'qtime_ms': result['avg_qtime_ms']
            })
            if verbose:
                print('.', end='', flush=True)
        if verbose:
            print(flush=True)
        stats = self.compile_search_results(term_results, '' in terms)
        self.test_log.search_stats[label] = stats
        return stats

    def compile_search_results(self, term_results, blank_included):
        qtime = sum([r['qtime_ms'] for r in term_results])
        return {
            'total_qtime_ms': round(qtime, 4),
            'avg_qtime_ms': round(qtime / len(term_results), 4),
            'term_results': term_results,
            'blank_included': blank_included
        }
