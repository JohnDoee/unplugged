"""
Coordinates plugins and handles the register
"""

import logging

logger = logging.getLogger(__name__)


class UnknownPluginTypeException(Exception):
    pass


class NotASubclassException(Exception):
    pass


class PluginHandler:
    def __init__(self):
        self.plugin_types = {}
        self.plugins = {}

    def register_plugin_type(self, plugin_interface):
        """
        Register a new plugin type.
        """
        plugin_type = plugin_interface.plugin_type
        if plugin_type in self.plugin_types:
            logger.info(f"Trying to register duplicate plugin_type:{plugin_type}")
            return

        logger.info("Registering plugin type: %r" % (plugin_type,))
        self.plugin_types[plugin_type] = plugin_interface
        self.plugins[plugin_type] = {}

    def register_plugin(self, cls):
        """
        Register a new plugin, making it usable.
        """
        plugin_type = cls.plugin_type
        name = cls.plugin_name

        if not name:
            raise AttributeError("Missing name")

        if plugin_type not in self.plugin_types:
            logger.error(f"Unknown plugin type {plugin_type} for plugin {name}")
            raise UnknownPluginTypeException(
                f"{plugin_type} is not a known plugin type"
            )

        if not issubclass(cls, self.plugin_types[plugin_type]):
            logger.error(f"{name} is not a subclass of {plugin_type}")
            raise NotASubclassException(f"{name} is not a subclass of {plugin_type}")

        if name in self.plugins[plugin_type]:
            logger.warning(f"Double registering plugin {name} of type {plugin_type}")

        logger.info(f"Registering plugin {name} of type {plugin_type}")
        self.plugins[plugin_type][name] = cls

    def get_all_plugins(self):
        for plugin_type in self.plugins.keys():
            for plugin in self.get_plugins(plugin_type):
                yield plugin

    def get_plugins(self, plugin_type):
        return sorted(
            self.plugins[plugin_type].values(), key=lambda x: getattr(x, "priority", 0)
        )

    def get_plugin_names(self, plugin_type):
        return self.plugins[plugin_type].keys()

    def get_plugin(self, plugin_type, name):
        return self.plugins[plugin_type].get(name)

    def get_plugin_type(self, plugin_type):
        return self.plugins[plugin_type]


pluginhandler = PluginHandler()
