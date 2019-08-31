import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save

from .models import Schedule
from .signals import plugin_loaded, plugin_unloaded

logger = logging.getLogger(__name__)


class ScheduleManager:
    def __init__(self):
        self.schedules = {}

    def plugin_loaded(self, sender, plugin, **kwargs):
        logger.debug(f"Creating schedules for {plugin}")
        for schedule in Schedule.objects.filter(plugin=plugin, enabled=True):
            self.reload_schedule(schedule)

    def plugin_unloaded(self, sender, plugin, **kwargs):
        logger.debug(f"Removing schedules for {plugin}")
        for schedule in Schedule.objects.filter(plugin=plugin, enabled=True):
            self.unload_schedule(schedule)

    def unload_schedule(self, schedule):
        logger.debug(f"Unloading schedule {schedule}")
        schedules = self.schedules.setdefault(schedule.plugin.pk, {})
        job = schedules.pop(schedule.pk, None)
        if job:
            job.remove()

    def schedule_modified(self, sender, instance, created, **kwargs):
        self.reload_schedule(instance)

    def schedule_deleted(self, sender, instance, **kwargs):
        self.unload_schedule(instance)

    def load_schedule(self, schedule):
        logger.debug(f"Loading schedule {schedule}")

        job = settings.SCHEDULER.add_job(
            self.trigger_schedule,
            schedule.get_trigger(),
            id=f"scheduler_{schedule.pk}",
            kwargs={"pk": schedule.pk},
        )
        schedules = self.schedules.setdefault(schedule.plugin.pk, {})
        schedules[schedule.pk] = job

    def reload_schedule(self, schedule):
        self.unload_schedule(schedule)
        if not schedule.enabled:
            return

        self.load_schedule(schedule)

    def trigger_schedule(self, pk):
        schedule = Schedule.objects.get(pk=pk)
        if not schedule.enabled:
            logger.warning(f"Trying to trigger disabled schedule {schedule.pk}")
            return

        plugin = schedule.plugin.get_plugin()
        command = plugin.get_command(schedule.command)
        kwargs = schedule.kwargs or {}
        kwargs = command.parse_kwargs(kwargs)
        kwargs["self"] = plugin

        try:
            _ = command.execute(kwargs)
        except Exception:
            logger.exception(
                f"Failed to execute {command} with args {kwargs} from schedule"
            )

    def start(self):
        logger.debug("Started schedule manager")
        post_delete.connect(self.schedule_deleted, sender=Schedule)
        post_save.connect(self.schedule_modified, sender=Schedule)
        plugin_loaded.connect(self.plugin_loaded)
        plugin_unloaded.connect(self.plugin_unloaded)

    def stop(self):
        logger.debug("Stopped schedule manager")
        post_delete.disconnect(self.schedule_deleted, sender=Schedule)
        post_save.disconnect(self.schedule_modified, sender=Schedule)
        plugin_loaded.disconnect(self.plugin_loaded)
        plugin_unloaded.disconnect(self.plugin_unloaded)


schedule_manager = ScheduleManager()
