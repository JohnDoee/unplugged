import json
import logging

from autobahn.twisted.wamp import ApplicationSession
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.utils.timezone import now

from .plugin import Plugin

logger = logging.getLogger(__name__)


class LogManager(models.Manager):
    def start_chain(self, plugin, action, user=None):
        if plugin is not None:
            if not isinstance(plugin, Plugin):
                plugin = plugin._plugin_obj
        logger.debug(
            f"New log chain started for plugin:{plugin!r} user:{user!r} action:{action}"
        )
        log = self.create(user=user, action=action, plugin=plugin)
        return LogChain(log)

    def cleanup_hanging_chains(self):
        logger.debug("Clearing up hanging log chains")
        self.filter(end_datetime__isnull=True).update(
            end_datetime=now(), status=Log.STATUS_FAILED
        )


class Log(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    plugin = models.ForeignKey(Plugin, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50, db_index=True)
    start_datetime = models.DateTimeField(auto_now_add=True)
    end_datetime = models.DateTimeField(null=True)
    progress = models.PositiveIntegerField(default=0)

    STATUS_PENDING = "pending"
    STATUS_ONGOING = "ongoing"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    status = models.CharField(
        default=STATUS_PENDING,
        choices=(
            (STATUS_PENDING, "Pending"),
            (STATUS_ONGOING, "Ongoing"),
            (STATUS_SUCCESS, "Success"),
            (STATUS_FAILED, "Failed"),
            (STATUS_CANCELLED, "Cancelled"),
        ),
        max_length=12,
    )

    objects = LogManager()

    def __str__(self):
        return f"user:{self.user!r} plugin:{self.plugin!r} progress:{self.progress} status:{self.status}"

    class JSONAPIMeta:
        resource_name = "log"


class LogMessage(models.Model):
    log = models.ForeignKey(
        Log, db_index=True, on_delete=models.CASCADE, related_name="log_messages"
    )
    datetime = models.DateTimeField(auto_now_add=True)
    msg = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-datetime",)

    class JSONAPIMeta:
        resource_name = "logmessage"


class LogChain:
    def __init__(self, log):
        self._log = log

    def log(self, progress=None, msg=""):
        modified = False

        if not isinstance(msg, str):
            msg = json.dumps(msg)

        if self._log.status == self._log.STATUS_PENDING:
            self._log.status = self._log.STATUS_ONGOING
            modified = True

        if progress is not None and self._log.progress != progress:
            self._log.progress = progress
            modified = True

        if modified:
            self._log.save()

        if msg:
            LogMessage.objects.create(log=self._log, msg=msg)

    def finish_chain(self, status):
        self._log.status = status
        self._log.end_datetime = now()
        self._log.save()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            status = Log.STATUS_FAILED
            self.log(msg=str(traceback))
        else:
            status = Log.STATUS_SUCCESS

        self.finish_chain(status)


class LogNotificationComponent(ApplicationSession):
    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)
        post_save.connect(self.new_log, sender=Log)
        post_save.connect(self.new_log_message, sender=LogMessage)

    def new_log(self, sender, instance, created, raw, *args, **kwargs):
        from ..views.log import LogSerializer

        self.publish(settings.WAMP_LOG_TOPIC, LogSerializer(instance).data)

    def new_log_message(self, sender, instance, created, raw, *args, **kwargs):
        from ..views.log import LogMessageSerializer

        self.publish(
            f"{settings.WAMP_LOG_TOPIC}.{instance.log_id}",
            LogMessageSerializer(instance).data,
        )
