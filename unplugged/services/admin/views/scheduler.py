from rest_framework import permissions, serializers, viewsets

from ....models import FailedToParseScheduleException, Schedule, parse_schedule_trigger
from .shared import ADMIN_RENDERER_CLASSES


class ScheduleSerializer(serializers.HyperlinkedModelSerializer):
    plugin_id = serializers.IntegerField()
    kwargs = serializers.DictField(default=dict)

    class Meta:
        model = Schedule
        fields = "__all__"
        read_only_fields = ["plugin"]

    class JSONAPIMeta:
        resource_name = "schedule"

    def validate(self, data):
        try:
            parse_schedule_trigger(data["method"], data["method_config"])
        except FailedToParseScheduleException as e:
            raise serializers.ValidationError(f"Failed to parse schedule: {e.args[0]}")

        return data


class ScheduleModelView(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None
    filterset_fields = ("plugin",)

    service = None
