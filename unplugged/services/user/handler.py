from django.conf.urls import url

from ...plugins import ServicePlugin
from ...schema import Schema
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
