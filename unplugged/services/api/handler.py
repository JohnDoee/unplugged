from django.conf.urls import url

from marshmallow import Schema

from ...plugins import ServicePlugin

from .views import APIConfigView


class APIConfigService(ServicePlugin):
    plugin_name = "api"
    config_schema = Schema

    def get_urls(self):
        return [url("^/?$", APIConfigView.as_view(service=self))]

    def unload(self):
        pass
