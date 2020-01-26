from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from wampyre.realm import realm_manager
from wampyre.transports.autowamp import ApplicationRunner

from .models import LogNotificationComponent, Plugin
from .scheduler import schedule_manager
from .signals import wamp_realm_created, wamp_realm_discarded


def handle_wampyre_callback(callback_type, realm):
    if callback_type == "create":
        wamp_realm_created.send(sender=realm)
    elif callback_type == "discard":
        wamp_realm_discarded.send(sender=realm)


def bootstrap_all():
    schedule_manager.start()
    Plugin.objects.bootstrap()

    content_type = ContentType.objects.get_for_model(Plugin)
    perm, _ = Permission.objects.get_or_create(
        content_type=content_type, codename="admin", defaults={"name": "Is admin"}
    )
    setattr(settings, "WAMP_LOG_TOPIC", f"group.{perm.id}.logs")

    realm_manager.register_callback(handle_wampyre_callback)

    ApplicationRunner(settings.WAMP_REALM).run(LogNotificationComponent)
