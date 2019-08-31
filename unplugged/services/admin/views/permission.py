from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import permissions, serializers, viewsets

from ....models import Plugin
from .shared import ADMIN_RENDERER_CLASSES, ServiceAwareHyperlinkedIdentityField


class PermissionSerializer(serializers.HyperlinkedModelSerializer):
    url = ServiceAwareHyperlinkedIdentityField(view_name="permission-detail")

    class Meta:
        model = Permission
        fields = ("name", "codename", "url")

    class JSONAPIMeta:
        resource_name = "permission"


class PermissionModelView(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None

    def get_queryset(self):
        return Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(Plugin),
            codename__startswith="service.",
        )
