from django.conf.urls import url

from ...plugins import ServicePlugin
from ...schema import Schema
from .views import APIConfigView


class APIServicePlugin(ServicePlugin):
    plugin_name = "api"
    config_schema = Schema

    def get_urls(self):
        return [url("^/?$", APIConfigView.as_view(service=self))]

    def unload(self):
        pass
