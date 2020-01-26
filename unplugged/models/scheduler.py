import re

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.db import models
from jsonfield import JSONField

from .plugin import Plugin


class FailedToParseScheduleException(Exception):
    pass


def parse_schedule_trigger(method, config):
    config = re.split(r" +", config)
    if method == "cron":
        fields = [
            "second",
            "minute",
            "hour",
            "day_of_week",
            "week",
            "day",
            "month",
            "year",
        ]
        try:
            kwargs = dict(zip(fields, config))
            return CronTrigger(**kwargs)
        except ValueError as e:
            raise FailedToParseScheduleException(*e.args)

    elif method == "interval":
        fields = ["weeks", "days", "hours", "minutes", "seconds"]
        try:
            kwargs = dict([c.split("=") for c in config])
            kwargs = {k: int(v) for (k, v) in kwargs.items()}
        except ValueError:
            raise FailedToParseScheduleException("Failed to parse config")

        unknown_keys = set(kwargs.keys()) - set(fields)
        if unknown_keys:
            raise FailedToParseScheduleException(
                f"Unknown keys found in config: {', '.join(unknown_keys)}"
            )

        try:
            return IntervalTrigger(**kwargs)
        except ValueError as e:
            raise FailedToParseScheduleException(*e.args)

    else:
        raise FailedToParseScheduleException(f"Unknown method: {method}")


class ScheduleManager(models.Manager):
    def ensure_schedule(
        self, method, method_config, command, kwargs, plugin, plugin_unique_id
    ):
        if not isinstance(plugin, Plugin):
            plugin = plugin._plugin_obj

        existing_schedules = self.filter(
            plugin=plugin, plugin_unique_id=plugin_unique_id
        )
        if existing_schedules:
            existing_schedule = existing_schedules[0]
            changed = False

            if existing_schedule.method != method:
                existing_schedule.method = method
                changed = True

            if existing_schedule.method_config != method_config:
                existing_schedule.method_config = method_config
                changed = True

            if existing_schedule.command != command:
                existing_schedule.command = command
                changed = True

            if existing_schedule.kwargs != kwargs:
                existing_schedule.kwargs = kwargs
                changed = True

            if not existing_schedule.enabled:
                existing_schedule.enabled = True
                changed = True

            if changed:
                existing_schedule.save()
        else:
            self.create(
                method=method,
                method_config=method_config,
                command=command,
                kwargs=kwargs,
                plugin=plugin,
                plugin_unique_id=plugin_unique_id,
            )


class Schedule(models.Model):
    METHOD_CRON = "cron"
    METHOD_INTERVAL = "interval"
    method = models.CharField(
        max_length=10, choices=((METHOD_CRON, "Cron"), (METHOD_INTERVAL, "Interval"))
    )
    method_config = models.CharField(max_length=500)

    command = models.CharField(max_length=200)
    kwargs = JSONField(blank=True)

    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    plugin_unique_id = models.CharField(
        max_length=100, db_index=True, null=True, blank=True
    )

    enabled = models.BooleanField(default=False)

    objects = ScheduleManager()

    def get_trigger(self):
        return parse_schedule_trigger(self.method, self.method_config)
