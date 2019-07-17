import logging

from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response
from rest_framework_json_api.renderers import JSONRenderer

from ..commands import CommandViewMixin
from ..jsonschema import dump_ui_schema
from ..libs.marshmallow_jsonschema import JSONSchema
from ..models import Plugin
from ..pluginhandler import pluginhandler

ADMIN_RENDERER_CLASSES = (JSONRenderer, BrowsableAPIRenderer)

logger = logging.getLogger(__name__)


class PluginBaseSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    plugin_name = serializers.CharField()
    plugin_type = serializers.CharField()
    schema = serializers.SerializerMethodField()
    ui_schema = serializers.SerializerMethodField()
    commands = serializers.SerializerMethodField()
    traits = serializers.SerializerMethodField()
    default_permission = serializers.CharField(default=None)

    class JSONAPIMeta:
        resource_name = "plugin_base"

    def get_commands(self, obj):
        if hasattr(obj, "get_jsonapi_commands"):
            return obj.get_jsonapi_commands()
        else:
            return []

    def get_schema(self, obj):
        schema = obj.config_schema()
        json_schema = JSONSchema()

        return json_schema.dump(schema)

    def get_ui_schema(self, obj):
        schema = obj.config_schema()
        return dump_ui_schema(schema)

    def get_traits(self, obj):
        if hasattr(obj, "__trait__"):
            return obj.__trait__
        else:
            return []

    def id(self, obj):
        return f"{obj.plugin_type}:{obj.plugin_name}"


class PluginBaseListView(viewsets.ViewSet):
    renderer_classes = ADMIN_RENDERER_CLASSES
    serializer_class = PluginBaseSerializer
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    resource_name = "plugin_base"

    def list(self, request):
        pluginbases = list(pluginhandler.get_all_plugins())
        serializer = self.serializer_class(pluginbases, many=True)
        return Response(serializer.data)


class PluginSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugin-detail")
    config = serializers.JSONField()

    class Meta:
        model = Plugin
        fields = "__all__"

    class JSONAPIMeta:
        resource_name = "plugin"


class PluginModelView(viewsets.ModelViewSet, CommandViewMixin):
    queryset = Plugin.objects.all()
    serializer_class = PluginSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    @action(methods=["post"], detail=False, url_path="reload", url_name="reload")
    def reload_all(self, request):
        Plugin.objects.unload_all_plugins()
        Plugin.objects.bootstrap()

        return Response({"status": "success", "message": "Modules reloaded"})

    @action(methods=["post"], detail=True)
    def command(self, request, pk=None):
        plugin = self.get_object().get_plugin()

        return self.call_command(request, plugin)

    @action(methods=["post"], detail=True, url_path="reload", url_name="reload-plugin")
    def reload_plugin(self, request, pk=None):
        plugin = self.get_object()
        plugin.reload_plugin()
        return Response({"message": "Plugin reloaded"})
