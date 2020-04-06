import logging
import threading
from collections import defaultdict

import wrapt
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from jsonfield import JSONField
from marshmallow import INCLUDE

from ..baseplugin import PluginBase
from ..pluginhandler import pluginhandler
from ..signals import plugin_loaded, plugin_unloaded

logger = logging.getLogger(__name__)


class PluginCache:
    def __init__(self):
        self.clear()

    def clear(self):
        self.plugins = defaultdict(dict)
        self.plugins_list = []

    def __contains__(self, key):
        if isinstance(key, tuple):
            plugin_type, name = key
        else:
            plugin_type = key.plugin_type
            name = key.name

        if name in self.plugins[plugin_type]:
            return True
        else:
            return False

    def get_plugin_by_keys(self, plugin_type, name):
        return self.plugins[plugin_type][name]

    def get_plugin(self, plugin):
        return self.plugins[plugin.plugin_type][plugin.name]

    def add_plugin(self, plugin):
        self.plugins_list.append(plugin)
        self.plugins[plugin.plugin_type][plugin.name] = plugin

    def remove_plugin(self, plugin):
        self.plugins_list.remove(plugin)
        del self.plugins[plugin.plugin_type][plugin.name]


PLUGIN_CACHE = PluginCache()
PLUGIN_CREATE_LOCK = threading.Lock()
PLUGIN_CREATE_LOCKS = {}


class PluginProxy(wrapt.ObjectProxy):
    _self_wrapped_info = None

    @property
    def __wrapped__(self):
        plugin_type, name = self._self_wrapped_info
        key = (plugin_type, name)
        if key in PLUGIN_CACHE:
            return PLUGIN_CACHE.get_plugin_by_keys(plugin_type, name)
        else:
            return None

    @__wrapped__.setter
    def __wrapped__(self, value):
        self._self_wrapped_info = (value.plugin_type, value.name)


class PluginManager(models.Manager):
    def bootstrap(self):
        logger.info("Bootstrapping plugin manager")
        for plugin_type in settings.PLUGIN_INITIALIZATION_ORDER:
            Plugin.objects.initialize_plugins(plugin_type)

    def initialize_plugins(self, plugin_type):
        logger.info(f"Initializing plugins of type {plugin_type}")
        for plugin in self.model.objects.filter(enabled=True, plugin_type=plugin_type):
            logger.debug(f"Initializing plugin {plugin}")
            plugin.get_plugin()

    def unload_all_plugins(self):
        logger.info("Unloading all plugins")
        for plugin in PLUGIN_CACHE.plugins_list[::-1]:
            plugin._plugin_obj.remove_plugin()

        PLUGIN_CACHE.clear()

    def get_plugin(self, pk):
        plugin = self.model.objects.get(pk=pk)
        if not plugin.enabled:
            logger.warning(f"Plugin {plugin.pk} is not enabled")
            return None

        return PluginProxy(plugin.get_plugin())

    def get_all_loaded_plugins(self):
        return PLUGIN_CACHE.plugins_list

    def get_plugin_by_name(self, plugin_type, name):
        plugin = self.model.objects.get(plugin_type=plugin_type, name=name)
        return self.get_plugin(plugin.pk)

    def get_plugins(self, plugin_type, plugin_name=None):
        plugins = self.model.objects.filter(plugin_type=plugin_type, enabled=True)
        if plugin_name:
            plugins = plugins.filter(plugin_name=plugin_name)

        return [self.get_plugin(p.pk) for p in plugins]


class Plugin(models.Model):  # TODO: ensure plugin unload / reload is good
    name = models.CharField(max_length=50)
    plugin_name = models.CharField(max_length=50)
    plugin_type = models.CharField(max_length=50)

    enabled = models.BooleanField(default=False)
    last_update = models.DateTimeField(auto_now=True)

    config = JSONField(blank=True, default={})

    objects = PluginManager()

    def create_plugin(self):
        PLUGIN_CREATE_LOCK.acquire()
        if self.pk in PLUGIN_CREATE_LOCKS:
            l = PLUGIN_CREATE_LOCKS[self.pk]
            PLUGIN_CREATE_LOCK.release()
            with l:
                return
        else:
            PLUGIN_CREATE_LOCKS[self.pk] = l = threading.Lock()
            l.acquire()
            PLUGIN_CREATE_LOCK.release()

        try:
            self._create_plugin()
        finally:
            with PLUGIN_CREATE_LOCK:
                del PLUGIN_CREATE_LOCKS[self.pk]
                l.release()

    def _create_plugin(self):
        logger.debug(
            f"Trying to create plugin from plugin_type:{self.plugin_type} and plugin_name:{self.plugin_name}"
        )
        plugin_class = pluginhandler.get_plugin(self.plugin_type, self.plugin_name)
        if plugin_class is None:
            logger.debug(
                f"Unknown plugin plugin_type:{self.plugin_type} and plugin_name:{self.plugin_name}"
            )
            return None

        schema = plugin_class.config_schema()
        plugin = plugin_class.__new__(plugin_class)
        plugin._related_plugins = []
        plugin.name = self.name

        config = schema.load(self.config, unknown=INCLUDE)

        def add_plugin_related(c):
            if isinstance(c, list):
                for v in c:
                    add_plugin_related(v)
            elif isinstance(c, dict):
                for v in c.values():
                    add_plugin_related(v)
            elif isinstance(c, PluginBase):
                if plugin not in c._related_plugins:
                    logger.debug(f"Adding related plugin {plugin} to {c}")
                    c._related_plugins.append(plugin)

        add_plugin_related(config)

        logger.debug(
            f"Creating plugin {self.plugin_type} / {self.plugin_name} / {self.name} with config {config} / {self.config}"
        )

        content_type = ContentType.objects.get_for_model(Plugin)
        perm, _ = Permission.objects.get_or_create(
            codename=f"{plugin.plugin_type}.{plugin.name}",
            content_type=content_type,
            defaults={
                "name": f"Can access plugin_type:{plugin.plugin_type} name:{plugin.name}"
            },
        )

        plugin.__init__(config)
        plugin._plugin_obj = self
        plugin._permission = perm

        if hasattr(plugin, "ready"):
            plugin.ready()

        PLUGIN_CACHE.add_plugin(plugin)
        plugin_loaded.send(sender=self.__class__, plugin=self)

    def is_plugin_loaded(self):
        return self in PLUGIN_CACHE

    def can_plugin_be_loaded(self):
        if self.is_plugin_loaded():
            return True

        try:
            self.get_plugin()
        except:
            logger.exception(f"Failed to load plugin {self}")
            return False
        else:
            return True

    def get_plugin(self):
        if not self.is_plugin_loaded():
            self.create_plugin()

        return PLUGIN_CACHE.get_plugin(self)

    def remove_plugin(self):
        if self.is_plugin_loaded():
            plugin = self.get_plugin()

            plugin_class = pluginhandler.get_plugin(self.plugin_type, self.plugin_name)
            schema = plugin_class.config_schema()
            config = schema.load(self.config, unknown=INCLUDE)

            def remove_plugin_related(c):
                if isinstance(c, list):
                    for v in c:
                        remove_plugin_related(v)
                elif isinstance(c, dict):
                    for v in c.values():
                        remove_plugin_related(v)
                elif isinstance(c, PluginBase):
                    if plugin in c._related_plugins:
                        c._related_plugins.remove(plugin)

            remove_plugin_related(config)

            plugin_unloaded.send(sender=self.__class__, plugin=self)
            PLUGIN_CACHE.remove_plugin(plugin)
            plugin.unload()

    def reload_plugin(self):
        logger.info(f"Reloading plugin {self}")
        self.remove_plugin()
        return self.get_plugin()

    def get_display_name(self):
        saps = self.simpleadminplugin_set.all()
        if self.config and self.config.get("display_name"):
            return self.config.get("display_name")
        elif saps and saps[0].get_display_name():
            return saps[0].get_display_name()
        else:
            return self.name

    class Meta:
        ordering = ("pk",)
        unique_together = (("name", "plugin_type"),)

    class JSONAPIMeta:
        resource_name = "plugin"

    def __str__(self):
        return f"{self.name} using {self.plugin_type}"
