import logging

import wrapt

from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models

from jsonfield import JSONField

from ..baseplugin import PluginBase
from ..signals import plugin_loaded, plugin_unloaded
from ..pluginhandler import pluginhandler


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


class PluginProxy(wrapt.ObjectProxy):
    @property
    def __wrapped__(self):
        plugin_type, name = self.__getattrib__('__wrapped_info__')
        key = (plugin_type, name)
        if key in PLUGIN_CACHE:
            return PLUGIN_CACHE.get_plugin_by_keys(plugin_type, name)
        else:
            return None

    @__wrapped__.setter
    def __wrapped__(self, value):
        self.__setattrib__('__wrapped_info__', value.plugin_type, value.name)


class PluginManager(models.Manager):
    def bootstrap(self):
        logger.info('Bootstrapping plugin manager')
        for plugin_type in settings.PLUGIN_INITIALIZATION_ORDER:
            Plugin.objects.initialize_plugins(plugin_type)

        from ..simpleadmin import scan_and_register_simpleadmin_template
        scan_and_register_simpleadmin_template()

    def initialize_plugins(self, plugin_type):
        logger.info('Initializing plugins of type %r' % (plugin_type, ))
        for plugin in self.model.objects.filter(enabled=True, plugin_type=plugin_type):
            logger.debug('Initializing plugin %r' % (plugin, ))
            plugin.get_plugin()

    def unload_all_plugins(self):
        logger.info('Unloading all plugins')
        for plugin in PLUGIN_CACHE.plugins_list[::-1]:
            plugin._plugin_obj.remove_plugin()

        PLUGIN_CACHE.clear()

    def get_plugin(self, pk):
        plugin = self.model.objects.get(pk=pk)
        if not plugin.enabled:
            logger.warning('Plugin %r is not enabled' % (plugin.pk), )
            return None

        return PluginProxy(plugin.get_plugin())

    def get_plugin_by_name(self, plugin_type, name):
        plugin = self.model.objects.get(plugin_type=plugin_type, name=name)
        return self.get_plugin(plugin.pk)

    def get_plugins(self, plugin_type, plugin_name=None):
        plugins = self.model.objects.filter(plugin_type=plugin_type, enabled=True)
        if plugin_name:
            plugins = plugins.filter(plugin_name=plugin_name)

        return [self.get_plugin(p.pk) for p in plugins]


class Plugin(models.Model): # TODO: ensure plugin unload / reload is good
    name = models.CharField(max_length=50)
    plugin_name = models.CharField(max_length=50)
    plugin_type = models.CharField(max_length=50)

    enabled = models.BooleanField(default=False)
    last_update = models.DateTimeField(auto_now=True)

    config = JSONField(blank=True, default={})

    objects = PluginManager()

    def create_plugin(self):
        logger.debug('Trying to create plugin from plugin_type:%s and plugin_name:%s' % (self.plugin_type, self.plugin_name, ))
        plugin_class = pluginhandler.get_plugin(self.plugin_type, self.plugin_name)
        if plugin_class is None:
            logger.debug('Unknown plugin plugin_type:%s and plugin_name:%s' % (self.plugin_type, self.plugin_name, ))
            return None

        schema = plugin_class.config_schema()
        plugin = plugin_class.__new__(plugin_class)
        plugin._related_plugins = []
        plugin.name = self.name

        PLUGIN_CACHE.add_plugin(plugin)

        config = schema.load(self.config).data

        def add_plugin_related(c):
            if isinstance(c, list):
                for v in c:
                    add_plugin_related(v)
            elif isinstance(c, dict):
                for v in c.values():
                    add_plugin_related(v)
            elif isinstance(c, PluginBase):
                if plugin not in c._related_plugins:
                    logger.debug('Adding related plugin %r to %r' % (plugin, c))
                    c._related_plugins.append(plugin)

        add_plugin_related(config)

        logger.debug('Creating plugin %s / %s / %s with config %r / %r' % (self.plugin_type, self.plugin_name, self.name, config, self.config))

        content_type = ContentType.objects.get_for_model(Plugin)
        perm, _ = Permission.objects.get_or_create(
            codename='%s.%s' % (plugin.plugin_type, plugin.name, ),
            content_type=content_type,
            defaults={
                'name': 'Can access plugin_type:%s name:%s' % (plugin.plugin_type, plugin.name, )
            }
        )

        plugin.__init__(config)
        plugin._plugin_obj = self
        plugin._permission = perm

        if hasattr(plugin, 'ready'):
            plugin.ready()

        plugin_loaded.send(sender=self.__class__, plugin=self)

    def is_plugin_loaded(self):
        return self in PLUGIN_CACHE

    def can_plugin_be_loaded(self):
        if self.is_plugin_loaded():
            return True

        try:
            self.get_plugin()
        except:
            logger.exception('Failed to load plugin %r' % (self, ))
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
            config = schema.load(self.config).data

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

            PLUGIN_CACHE.remove_plugin(plugin)
            plugin.unload()

    def reload_plugin(self):
        logger.info('Reloading plugin %r' % (self, ))
        self.remove_plugin()
        return self.get_plugin()

    def get_display_name(self):
        return self.config and self.config.get('display_name') or self.name

    class Meta:
        ordering = ('pk', )
        unique_together = (('name', 'plugin_type',),)

    def __str__(self):
        return u'%s using %s' % (self.name, self.plugin_type)
