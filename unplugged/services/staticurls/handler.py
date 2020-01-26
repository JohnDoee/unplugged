import logging

from django.urls import include, path

from ...jsonapi import JSONAPIObject, JSONAPIRoot
from ...pluginhandler import pluginhandler
from ...plugins import ServicePlugin
from ...schema import Schema
from .views import StaticUrlsView

logger = logging.getLogger(__name__)


class StaticUrlsServicePlugin(ServicePlugin):
    plugin_name = "staticurls"
    config_schema = Schema
    plugin_url_root = None

    def get_urls(self):
        urls = [path("", StaticUrlsView.as_view(service=self))]
        root = JSONAPIRoot()
        for plugin_cls in pluginhandler.get_all_plugins():
            if not hasattr(plugin_cls, "get_static_urls"):
                continue
            static_urls = plugin_cls.get_static_urls()

            if not static_urls:
                continue

            logger.debug(
                f"Got {len(static_urls)} urls from {plugin_cls.plugin_type}/{plugin_cls.plugin_name}"
            )
            url = f"{plugin_cls.plugin_type}/{plugin_cls.plugin_name}/"
            urls.append(path(url, include(static_urls)))

            links = {"self": f"/{plugin_cls.name}/"}
            obj = JSONAPIObject(
                plugin_cls.plugin_type, plugin_cls.plugin_name, links=links
            )
            root.append(obj)

        self.plugin_url_root = root
        return urls

    def unload(self):
        pass
