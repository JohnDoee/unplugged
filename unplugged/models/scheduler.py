import re

from django.db import models

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from jsonfield import JSONField

from .plugin import Plugin


class FailedToParseScheduleException(Exception):
    pass


def parse_schedule_trigger(method, config):
    config = re.split(r' +', config)
    if method == 'cron':
        fields = ['second', 'minute', 'hour', 'day_of_week', 'week', 'day', 'month', 'year']
        try:
            kwargs = dict(zip(fields, config))
            return CronTrigger(**kwargs)
        except ValueError as e:
            raise FailedToParseScheduleException(*e.args)

    elif method == 'interval':
        fields = ['weeks', 'days', 'hours', 'minutes', 'seconds']
        try:
            kwargs = dict([c.split('=') for c in config])
        except ValueError:
            raise FailedToParseScheduleException('Failed to parse config')

        unknown_keys = set(kwargs.keys()) - set(fields)
        if unknown_keys:
            raise FailedToParseScheduleException('Unknown keys found in config: %s' % (', '.join(unknown_keys), ))

        try:
            return IntervalTrigger(**kwargs)
        except ValueError as e:
            raise FailedToParseScheduleException(*e.args)

    else:
        raise FailedToParseScheduleException('Unknown method: %s' % (method, ))


class Schedule(models.Model):
    METHOD_CRON = 'cron'
    METHOD_INTERVAL = 'interval'
    method = models.CharField(max_length=10, choices=(
        (METHOD_CRON, 'Cron'),
        (METHOD_INTERVAL, 'Interval'),
    ))
    method_config = models.CharField(max_length=500)

    command = models.CharField(max_length=200)
    kwargs = JSONField(blank=True)

    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    plugin_unique_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    enabled = models.BooleanField(default=False)

    def get_trigger(self):
        return parse_schedule_trigger(self.method, self.method_config)
