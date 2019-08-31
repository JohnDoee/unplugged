import logging

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ...jsonapi import JSONAPIObject, JSONAPIRoot
from ...models import Plugin

logger = logging.getLogger(__name__)


class APIConfigView(APIView):
    service = None

    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        root = JSONAPIRoot()

        for plugin in Plugin.objects.filter(enabled=True, plugin_type="service"):
            links = {"self": request.build_absolute_uri("/%s/" % plugin.name)}
            plugin_type = "%s_%s" % (plugin.plugin_type, plugin.plugin_name)

            plugin_obj = plugin.get_plugin()
            permission_obj = JSONAPIObject("permission", "access_%s" % (plugin.name,))
            urls = plugin_obj.get_urls()

            permission_obj["can_access"] = False
            if urls:
                for pattern in urls:
                    view_pattern = pattern.resolve("")
                    if view_pattern:
                        func = view_pattern.func
                        view = func.view_class(**func.view_initkwargs)
                        permissions = [
                            permission() for permission in view.permission_classes
                        ]
                        for permission in permissions:
                            if permission.has_permission(request, view):
                                permission_obj["can_access"] = True
                        break
            else:  # TODO: add websocket support
                permission_obj["can_access"] = True

            if not permission_obj[
                "can_access"
            ]:  # Not sure if we should leak inaccessible services...
                continue

            obj = JSONAPIObject(plugin_type, plugin.name, links=links)
            obj["display_name"] = plugin.config.get("display_name", plugin.name)
            root.append(obj)

            obj.add_relationship("permission", permission_obj, local=True)

        return Response(root.serialize(request))
