from rest_framework import permissions, serializers, viewsets
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework_json_api.renderers import JSONRenderer

from ..models import Log, LogMessage, Plugin

ADMIN_RENDERER_CLASSES = (JSONRenderer, BrowsableAPIRenderer)


class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = ("id", "name", "plugin_name", "plugin_type")


class LogMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogMessage
        fields = ("id", "datetime", "msg")

    class JSONAPIMeta:
        resource_name = "logmessage"


class LogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user__username", allow_null=True)
    plugin = PluginSerializer(allow_null=True)

    included_serializers = {
        "log_messages": LogMessageSerializer,
        "plugin": PluginSerializer,
    }

    class Meta:
        model = Log
        fields = (
            "id",
            "username",
            "plugin",
            "action",
            "start_datetime",
            "end_datetime",
            "progress",
            "status",
        )

    class JSONAPIMeta:
        resource_name = "log"


class LogDetailSerializer(LogSerializer):
    class Meta:
        model = Log
        fields = (
            "id",
            "username",
            "plugin",
            "action",
            "start_datetime",
            "end_datetime",
            "progress",
            "status",
            "log_messages",
        )

    class JSONAPIMeta:
        resource_name = "log"
        included_resources = ["log_messages", "plugin"]


class LogModelView(viewsets.ReadOnlyModelViewSet):
    queryset = Log.objects.all().order_by("-id")
    serializer_class = LogSerializer
    serializer_detail_class = LogDetailSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return self.serializer_detail_class
        return super().get_serializer_class()
