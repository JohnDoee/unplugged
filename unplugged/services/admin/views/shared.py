from rest_framework import serializers
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework_json_api.renderers import JSONRenderer

__all__ = ["ServiceAwareHyperlinkedIdentityField", "ADMIN_RENDERER_CLASSES"]

ADMIN_RENDERER_CLASSES = (JSONRenderer, BrowsableAPIRenderer)


class ServiceAwareHyperlinkedIdentityField(serializers.HyperlinkedIdentityField):
    _view_name = None

    @property
    def view_name(self):
        if hasattr(self, "parent"):
            module = self.context["view"].__class__.__module__.split(".")[0]
            return f"{module}:{self.context['view'].service.name}:{self._view_name}"
        else:
            return self._view_name

    @view_name.setter
    def view_name(self, value):
        self._view_name = value
