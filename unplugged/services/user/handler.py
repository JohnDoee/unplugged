from django.conf.urls import url
from marshmallow import Schema

from ...plugins import ServicePlugin
from .views import AuthView, LogoutView, UserView


class UserServicePlugin(ServicePlugin):
    plugin_name = "user"

    config_schema = Schema

    def get_urls(self):
        return [
            url("^/?$", UserView.as_view(service=self)),
            url("^auth/?$", AuthView.as_view(service=self)),
            url("^logout/?$", LogoutView.as_view(service=self)),
        ]

    def unload(self):
        pass
