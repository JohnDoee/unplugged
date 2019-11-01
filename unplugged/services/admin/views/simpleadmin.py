import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, reverse
from django.utils.text import slugify
from marshmallow import INCLUDE
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from ....jsonapi import JSONAPIObject, JSONAPIRoot
from ....jsonschema import dump_ui_schema
from ....libs.marshmallow_jsonschema import JSONSchema
from ....schema import ValidationError
from ..models import NameAlreadyInUseException, SimpleAdminPlugin, SimpleAdminTemplate
from .shared import ADMIN_RENDERER_CLASSES, ServiceAwareHyperlinkedIdentityField

logger = logging.getLogger(__name__)


class SimpleAdminTemplateSerializer(serializers.HyperlinkedModelSerializer):
    schema = serializers.SerializerMethodField(source="template")
    ui_schema = serializers.SerializerMethodField(source="template")

    class Meta:
        model = SimpleAdminTemplate
        fields = (
            "display_name",
            "description",
            "template_id",
            "plugin_type",
            "plugin_name",
            "schema",
            "ui_schema",
        )

    class JSONAPIMeta:
        resource_name = "simpleadmin_template"

    def get_schema(self, obj):
        json_schema = JSONSchema()
        return json_schema.dump(obj.config_schema())

    def get_ui_schema(self, obj):
        schema = obj.config_schema()
        return dump_ui_schema(schema)


class SimpleAdminTemplateModelView(viewsets.ModelViewSet):
    """
    List of all possible templates we can create listing derivatives from.
    """

    queryset = SimpleAdminTemplate.objects.all()
    serializer_class = SimpleAdminTemplateSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None


class SimpleAdminPluginSerializer(serializers.HyperlinkedModelSerializer):
    url = ServiceAwareHyperlinkedIdentityField(view_name="simpleadmin_plugin-detail")
    template = SimpleAdminTemplateSerializer()
    plugin_type = serializers.CharField(read_only=True, source="plugin.plugin_type")
    plugin_name = serializers.CharField(read_only=True, source="plugin.plugin_name")
    config = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = SimpleAdminPlugin
        fields = (
            "name",
            "template",
            "template_id",
            "plugin_id",
            "plugin_type",
            "plugin_name",
            "url",
            "config",
            "display_name",
        )

    class JSONAPIMeta:
        resource_name = "simpleadmin_plugin"

    def get_config(self, obj):
        return obj.pull_form_data()

    def get_display_name(self, obj):
        return obj.get_display_name()


class SimpleAdminPluginCreateSerializer(serializers.ModelSerializer):
    config = serializers.DictField(write_only=True)  # verify it matches schema
    template_id = serializers.IntegerField()
    plugin_type = serializers.CharField()
    plugin_name = serializers.CharField()

    class Meta:
        model = SimpleAdminPlugin
        fields = ("config", "template_id", "plugin_type", "plugin_name")

    class JSONAPIMeta:
        resource_name = "simpleadmin_plugin"


class SimpleAdminPluginPrioritySerializer(serializers.Serializer):
    priorities = serializers.ListField(child=serializers.IntegerField())


class SimpleAdminPluginModelView(viewsets.ModelViewSet):
    """
    What is currently controlled by simpleadmin and where?
    """

    queryset = SimpleAdminPlugin.objects.all().order_by("priority")
    serializer_class = SimpleAdminPluginSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None

    @action(methods=["post"], detail=False)
    def set_priorities(self, request):
        serializer = SimpleAdminPluginPrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plugins = set()
        priorities = {}
        for i, plugin_id in enumerate(serializer.validated_data["priorities"]):
            sap = SimpleAdminPlugin.objects.get(id=plugin_id)
            sap.priority = i
            sap.save(update_fields=["priority"])

            plugins.add(sap.plugin)
            priorities[(sap.plugin, sap.name)] = i
            priorities[(sap.plugin, sap.pk)] = i

        for plugin in plugins:

            def get_priority(p):
                k = (plugin, p["name"])
                if k in priorities:
                    return priorities[k]

                k = (plugin, p["_simpleadminplugin_id"])
                if k in priorities:
                    return priorities[k]

                return 100

            plugin.config[sap.template.modify_key] = sorted(
                plugin.config[sap.template.modify_key], key=get_priority
            )
            plugin.save()

        return Response({"status": "success", "message": "Priority set"})

    @action(methods=["get"], detail=True)
    def in_use_by(self, request, pk=None):
        plugin = self.get_object()

        return Response(
            [
                {
                    "name": p.name,
                    "plugin_name": p.plugin_name,
                    "plugin_type": p.plugin_type,
                }
                for p in plugin.check_in_use_by()
            ]
        )

    def get_serializer_class(self):
        if self.action in ["create", "update"]:
            return SimpleAdminPluginCreateSerializer
        else:
            return super(SimpleAdminPluginModelView, self).get_serializer_class()

    def generate_name(self, serializer):
        name = serializer.initial_data["config"].get("name")
        if not name:
            name = slugify(serializer.initial_data["config"].get("display_name"))
        return name

    def perform_create(self, serializer):
        template = get_object_or_404(
            SimpleAdminTemplate, pk=serializer.initial_data["template_id"]
        )
        try:
            _ = template.config_schema().load(
                serializer.initial_data["config"], unknown=INCLUDE
            )
        except ValidationError as err:
            return Response(err.messages, status=status.HTTP_400_BAD_REQUEST)

        name = self.generate_name(serializer)

        try:
            sap = template.add_plugin(
                name, serializer.initial_data["config"].get(template.modify_key)
            )
        except NameAlreadyInUseException as e:
            return Response({"name": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        if not sap:
            raise Http404

        try:
            sap.update_plugin(serializer.initial_data["config"])
        except NameAlreadyInUseException as e:
            return Response({"name": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        sap.save()

        return sap

    def perform_update(self, serializer):
        sap = serializer.instance
        try:
            _ = sap.template.config_schema().load(
                serializer.initial_data["config"], unknown=INCLUDE
            )
        except ValidationError as err:
            return Response(err.messages, status=status.HTTP_400_BAD_REQUEST)

        name = self.generate_name(serializer)
        if sap.name != name:
            logger.debug("Trying to rename %s to %s" % (sap.name, name))
            serializer.initial_data["config"]["name"] = name

        try:
            sap.update_plugin(serializer.initial_data["config"])
        except NameAlreadyInUseException as e:
            return Response({"name": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        sap.save()

    def perform_destroy(self, instance):
        instance.delete_plugin()
        instance.delete()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        r = self.perform_update(serializer)
        if isinstance(r, Response):
            return r

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        serializer_class = super(
            SimpleAdminPluginModelView, self
        ).get_serializer_class()
        return Response(
            serializer_class(
                instance=instance, context={"request": request, "view": self}
            ).data
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = self.perform_create(serializer)
        if isinstance(obj, Response):
            return obj
        headers = self.get_success_headers(serializer.data)
        serializer_class = super(
            SimpleAdminPluginModelView, self
        ).get_serializer_class()
        return Response(
            serializer_class(
                instance=obj, context={"request": request, "view": self}
            ).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class ShowAdminUrlsView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    router = None
    urls = None
    service = None

    def get(self, request):
        root = JSONAPIRoot()

        for url in self.urls:
            if url.name.endswith("-detail"):
                continue

            resource_name = url.callback.cls.serializer_class.JSONAPIMeta.resource_name
            try:
                view_url = reverse("unplugged:%s:%s" % (self.service.name, url.name))
            except NoReverseMatch:
                continue

            if url.name.endswith("-list"):
                view_id = resource_name
            else:
                view_id = "%s_%s" % (
                    resource_name,
                    url.name.split("-", 1)[1].replace("-", "_"),
                )

            links = {"self": request.build_absolute_uri(view_url)}
            plugin_type = "admin_%s" % (view_id,)
            obj = JSONAPIObject(plugin_type, resource_name, links=links)
            root.append(obj)

        return Response(root.serialize(request))
