import logging
from abc import ABCMeta, abstractproperty

from .commands import CommandBaseMeta
from .pluginhandler import pluginhandler
from .schema import fields

logger = logging.getLogger(__name__)


def register_plugin(cls):
    """Autoregisters the plugin with the handler"""
    plugin_name = getattr(cls, "plugin_name", None)
    plugin_type = getattr(cls, "plugin_type", None)

    if isinstance(plugin_type, str):
        if isinstance(plugin_name, str):
            pluginhandler.register_plugin(cls)
        else:
            pluginhandler.register_plugin_type(cls)


class PluginBaseMeta(ABCMeta, CommandBaseMeta):
    def __new__(mcls, name, bases, namespace):
        cls = super(PluginBaseMeta, mcls).__new__(mcls, name, bases, namespace)
        register_plugin(cls)
        return cls

    @property
    def pk(self):
        return "%s:%s" % (self.plugin_type, self.plugin_name)


class PluginBase(metaclass=PluginBaseMeta):
    __commands__ = None
    __traits__ = []

    _related_plugins = None
    _plugin_obj = None

    name = None

    def __init__(self, config):
        """
        Instantiates the plugin with a config
        """
        self.config = config

    @abstractproperty
    def plugin_type(self):
        """
        Name of plugin type
        """
        raise NotImplementedError

    @abstractproperty
    def plugin_name(self):
        """
        Name of plugin
        """
        raise NotImplementedError

    def unload(self):
        """
        Unloads the plugin instance and shuts it down.
        """
        pass

    @abstractproperty
    def config_schema(self):
        """
        Marshmallow Schema used to configure the plugin.
        """
        raise NotImplementedError


class RelatedPluginField(fields.Field):
    def _jsonschema_type_mapping(self):
        from .models import Plugin

        plugins = Plugin.objects.filter(enabled=True)

        plugin_type = getattr(self.metadata.get("plugin_type"), "plugin_type", None)
        if plugin_type:
            plugins = plugins.filter(plugin_type=plugin_type)

        plugin_name = getattr(self.metadata.get("plugin_name"), "plugin_name", None)
        if plugin_name:
            plugins = plugins.filter(plugin_name=plugin_name)

        traits_required = set(self.metadata.get("traits", []))
        plugins = [
            p
            for p in plugins
            if p.can_plugin_be_loaded()
            and not traits_required - set(p.get_plugin().__traits__)
        ]

        if not plugins:
            return {"type": "number", "enum": [0], "enumNames": ["No plugins added"]}

        return {
            "type": "number",
            "enum": [p.pk for p in plugins],
            "enumNames": [p.get_display_name() for p in plugins],
        }

    def _deserialize(self, value, attr, data, **kwargs):
        from .models import Plugin

        logger.debug("Trying to resolve related %r" % (value,))
        try:
            return Plugin.objects.get_plugin(pk=value)
        except Plugin.DoesNotExist:
            return None


class DjangoModelField(fields.Field):
    def _jsonschema_type_mapping(self):
        queryset = self.metadata.get("queryset", [])
        name_field = self.metadata.get("name_field", "pk")
        objs = [obj for obj in queryset]

        return {
            "type": "number",
            "enum": [obj.pk for obj in objs],
            "enumNames": [getattr(obj, name_field) for obj in objs],
        }

    def _deserialize(self, value, attr, data, **kwargs):
        queryset = self.metadata.get("queryset", [])
        logger.debug("Trying to resolve object %r" % (value,))
        try:
            return queryset.get(pk=value)
        except queryset.model.DoesNotExist:
            return None
