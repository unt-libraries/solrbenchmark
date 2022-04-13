"""
Contains a generic utilty class for timing events.
"""

from datetime import datetime, timedelta

import logging


class Timer(object):
    def __init__(self, logger=None, max_decimal_places=8):
        self.timings = []
        self.event_stack = {}
        self.logger = logger
        self.enabled = True
        self.max_decimal_places = max_decimal_places

    def round(self, number):
        return round(number, self.max_decimal_places)

    def format_timing(self, label, timing):
        as_seconds = self.round(timing.total_seconds())
        return '{: >40} {: >10.6f}s'.format(label, as_seconds)

    def start(self, label):
        if self.enabled:
            now = datetime.now()
            self.event_stack[label] = now

    def end(self, label):
        if self.enabled:
            if label in self.event_stack:
                now = datetime.now()
                event_start = self.event_stack.pop(label)
                timing = now - event_start
                self.timings.append((label, timing))
                if self.logger:
                    self.logger.info(self.format_timing(label, timing))
            elif self.logger:
                self.logger.info('{: >40} {: >11}'.format(label, 'N/A'))

    def compile_statistics(self, convert_to_seconds=False):
        statistics = {
            'event_timings': {},
            'event_totals': {},
            'event_averages': {}
        }
        default_secs = 0 if convert_to_seconds else timedelta()
        for l, t in self.timings:
            timing = statistics['event_timings'].get(l, [])
            secs = self.round(t.total_seconds()) if convert_to_seconds else t
            timing.append(secs)
            statistics['event_timings'][l] = timing
            total = statistics['event_totals'].get(l, default_secs) + secs
            avg = total / len(timing)
            if convert_to_seconds:
                total = self.round(total)
                avg = self.round(avg)
            statistics['event_totals'][l] = total
            statistics['event_averages'][l] = avg
        return statistics

    def report(self):
        statistics = self.compile_statistics()
        if self.logger:
            self.logger.info('FINAL TIMING REPORT')
            self.logger.info('    TOTALS')
            for l, total in statistics['event_totals'].items():
                self.logger.info(self.format_timing(l, total))
            self.logger.info('    AVERAGES')
            for l, avg in statistics['event_averages'].items():
                self.logger.info(self.format_timing(l, avg))
