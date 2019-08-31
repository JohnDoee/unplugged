import logging

from django.conf import settings
from django.conf.urls import include, url
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import path
from django.utils.text import slugify
from rest_framework.permissions import BasePermission

from ..baseplugin import PluginBase
from ..routing import register_channels, unregister_channel
from ..urls import register_urlpatterns, unregister_urlpattern

logger = logging.getLogger(__name__)


class CascadingPermission(BasePermission):
    """
    Tries to check up the dependency tree to see
    if there is a service allowing this plugin.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        checked = []

        def check_up(plugin):
            perm_name = "unplugged.%s.%s" % (plugin.plugin_type, plugin.name)
            checked.append(plugin)
            logger.debug(
                "Checking permission %r for user %r" % (perm_name, request.user)
            )
            if request.user.has_perm(perm_name):
                return True

            for sub_plugin in plugin._related_plugins:
                if sub_plugin in checked:
                    continue

                if check_up(sub_plugin):
                    return True

        return bool(check_up(view.service))


class DefaultPermission:
    IGNORE = "ignore"
    ALLOW = "allow"
    DENY = "deny"


class ServicePlugin(PluginBase):
    plugin_type = "service"
    mount_at_root = False
    default_permission = DefaultPermission.IGNORE

    def get_urls(self):
        """
        Returns urls to be registered.
        """
        return []

    def get_channels(self):
        """
        Returns channels to be registered.
        """
        return []

    def unload(self):
        unregister_urlpattern(r"^%s/" % (slugify(self.name),))
        unregister_channel(r"^%s/" % (slugify(self.name),))

    def ready(self):
        service_urls = self.get_urls()
        if service_urls:
            path_fragment = r"^%s/" % (slugify(self.name),)
            urls = [
                url(
                    path_fragment,
                    include((service_urls, self.name), namespace=self.name),
                )
            ]

            if self.mount_at_root:
                logger.info("Mounting %s at root" % (self.name,))
                urls.append(url("^/?$", include(service_urls)))

            register_urlpatterns(urls)

        channels = self.get_channels()
        if channels:
            path_fragment = r"%s/" % (slugify(self.name),)
            real_channels = []
            for channel in channels:
                if len(channel) == 2:
                    p, consumer = channel
                    kwargs = None
                elif len(channel) == 3:
                    p, consumer, kwargs = channel

                real_channels.append(path(path_fragment + p, consumer, kwargs=kwargs))
            register_channels(real_channels)


@receiver(
    post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="set_initial_permissions"
)
def set_initial_permissions(sender, instance, created, **kwargs):
    if not created:
        return

    from ..models import Plugin

    logger.info("Setting default permissions for user %r" % (instance,))
    for plugin in Plugin.objects.filter(enabled=True, plugin_type="service"):
        plugin_obj = plugin.get_plugin()
        if plugin_obj.default_permission == "allow":
            instance.user_permissions.add(plugin_obj._permission)
