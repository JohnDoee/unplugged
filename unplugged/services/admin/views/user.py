import logging

from django.contrib.auth.models import Permission, User
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ....models import Plugin
from .shared import ADMIN_RENDERER_CLASSES, ServiceAwareHyperlinkedIdentityField

logger = logging.getLogger(__name__)


class UserPasswordSerializer(serializers.Serializer):
    password = serializers.CharField()


class UserPermissionsSerializer(serializers.Serializer):
    permissions = serializers.ListField(child=serializers.CharField())


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = ServiceAwareHyperlinkedIdentityField(view_name="user-detail")
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        exclude = ("password", "groups", "user_permissions")

    class JSONAPIMeta:
        resource_name = "user"

    def get_permissions(self, obj):
        content_type = ContentType.objects.get_for_model(Plugin)
        return list(
            obj.user_permissions.filter(content_type=content_type).values_list(
                "codename", flat=True
            )
        )


class UserModelView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None

    @action(methods=["post"], detail=True)
    def set_password(self, request, pk=None):
        user = self.get_object()
        serializer = UserPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        password = serializer.data["password"]
        try:
            validate_password(password, user)
        except ValidationError:
            return Response(
                {"message": "Please choose a more complex password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()

        return Response({"message": "User password changed successfully"})

    @action(methods=["post"], detail=True)
    def set_permissions(self, request, pk=None):
        user = self.get_object()
        serializer = UserPermissionsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content_type = ContentType.objects.get_for_model(Plugin)
        current_permissions = set(
            user.user_permissions.filter(content_type=content_type).values_list(
                "codename", flat=True
            )
        )
        permissions = set(serializer.data["permissions"])

        for codename in current_permissions - permissions:
            try:
                permission = Permission.objects.get(
                    content_type=content_type, codename=codename
                )
            except:
                logger.warning("Unknown permission: %s" % (codename))
                continue

            user.user_permissions.remove(permission)

        for codename in permissions - current_permissions:
            try:
                permission = Permission.objects.get(
                    content_type=content_type, codename=codename
                )
            except:
                logger.warning("Unknown permission: %s" % (codename))
                continue

            user.user_permissions.add(permission)

        return Response(
            {"status": "success", "message": "Permissions changed successfully"}
        )
