import logging
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import namedtuple
from pathlib import Path

import pkg_resources
import twine.exceptions
import twine.package

from django.conf import settings
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ....models import Plugin
from ..models import ExternalPlugin
from .shared import ADMIN_RENDERER_CLASSES, ServiceAwareHyperlinkedIdentityField

logger = logging.getLogger(__name__)


def extract_package_info_from_path(path):
    try:
        return twine.package.PackageFile.from_filename(str(path), None)
    except (twine.exceptions.TwineException, zipfile.BadZipFile, ValueError):
        return None


def extract_package_info(file):
    with tempfile.TemporaryDirectory() as tmp_folder:
        p = tmp_folder / Path(file.name)
        file.file.seek(0)
        with p.open("wb") as f:
            f.write(file.file.read())

        return extract_package_info_from_path(p)


class ExternalPluginSerializer(serializers.ModelSerializer):
    url = ServiceAwareHyperlinkedIdentityField(view_name="externalplugin-detail")
    file = serializers.FileField(source="plugin_file", write_only=True)
    keywords = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = ExternalPlugin
        fields = (
            "url",
            "file",
            "name",
            "version",
            "description",
            "keywords",
        )
        read_only_fields = (
            "url",
            "name",
            "version",
            "description",
            "keywords",
        )

    class JSONAPIMeta:
        resource_name = "externalplugin"

    def validate_file(self, value):
        dist = extract_package_info(value)
        if not dist:
            raise serializers.ValidationError("Unable to parse plugin")

        return value

    def create(self, validated_data):
        dist = extract_package_info(validated_data["plugin_file"])
        metadata = dist.metadata_dictionary()
        keywords = metadata["keywords"]
        if keywords:
            keywords = keywords.split(",")
        else:
            keywords = []

        return ExternalPlugin.objects.create(
            name=metadata["name"],
            version=metadata["version"],
            description=metadata["summary"],
            keywords=keywords,
            plugin_file=validated_data["plugin_file"],
        )


class ShutdownResponse(Response):
    def close(self):
        super().close()

        Plugin.objects.unload_all_plugins()
        if settings.TWISTD_PIDFILE and os.path.isfile(settings.TWISTD_PIDFILE):
            os.unlink(settings.TWISTD_PIDFILE)
        os.execl(sys.executable, sys.executable, *sys.argv)


class ExternalPluginModelView(viewsets.ModelViewSet):
    queryset = ExternalPlugin.objects.all()
    serializer_class = ExternalPluginSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None

    @action(methods=["post"], detail=True)
    def install(self, request, pk=None):
        obj = self.get_object()

        result = obj.install()
        if result:
            return Response({"status": "error", "message": result})
        else:
            return Response({"status": "success", "message": "Plugin copied"})

    @action(methods=["post"], detail=False)
    def restart_server(self, request):
        return ShutdownResponse({"status": "success", "message": "Restarting server"})


class LoadedPluginSerializer(serializers.Serializer):
    url = ServiceAwareHyperlinkedIdentityField(view_name="loadedplugin-detail")
    filename = serializers.CharField()
    name = serializers.CharField()
    version = serializers.CharField()
    description = serializers.CharField()
    keywords = serializers.ListField(child=serializers.CharField())
    installed_version = serializers.CharField()
    loaded = serializers.BooleanField()
    orphaned = serializers.BooleanField()
    in_use = serializers.BooleanField()

    class JSONAPIMeta:
        resource_name = "loadedplugin"


LoadedPlugin = namedtuple(
    "LoadedPlugin",
    [
        "pk",
        "filename",
        "name",
        "version",
        "description",
        "keywords",
        "installed_version",
        "loaded",
        "orphaned",
        "in_use",
    ],
)


class LoadedPluginView(viewsets.ViewSet):
    serializer_class = LoadedPluginSerializer
    renderer_classes = ADMIN_RENDERER_CLASSES
    permission_classes = (permissions.IsAdminUser,)
    pagination_class = None

    service = None

    resource_name = "loadedplugin"

    def get_installed_plugins(self):
        all_plugins = Plugin.objects.get_all_loaded_plugins()
        loaded_modules = set()
        for plugin in all_plugins:
            module = plugin.__module__
            while module:
                module = module.rsplit(".", 1)[0]
                loaded_modules.add(module)
                if "." not in module:
                    break

        package_root = Path(settings.PACKAGE_ROOT)
        installed_plugins = {}
        working_set = pkg_resources.WorkingSet()
        for entry_point in working_set.iter_entry_points(settings.PLUGIN_ENTRY_POINT):
            if entry_point.name != "app":
                continue
            installed_plugins[entry_point.dist.project_name] = (
                entry_point.dist.version,
                entry_point.module_name,
            )

        plugins = [
            p
            for p in package_root.iterdir()
            if p.is_file()
            and p.suffix in [".zip", ".whl"]
            or p.name.endswith(".tar.gz")
        ]

        found_installed_plugins = []
        result = []
        for plugin in plugins:
            package_info = extract_package_info_from_path(plugin)
            if not package_info:
                continue

            metadata = package_info.metadata_dictionary()
            keywords = metadata["keywords"]
            if keywords:
                keywords = keywords.split(",")
            else:
                keywords = []

            plugin_info = {
                "pk": metadata["name"],
                "filename": plugin.name,
                "name": metadata["name"],
                "version": metadata["version"],
                "description": metadata["summary"],
                "keywords": keywords,
                "installed_version": None,
                "loaded": False,
                "orphaned": False,
                "in_use": False,
            }

            if metadata["name"] in installed_plugins:
                found_installed_plugins.append(metadata["name"])
                plugin_info["installed_version"], module_name = installed_plugins[
                    metadata["name"]
                ]
                if module_name in settings.INSTALLED_APPS:
                    plugin_info["loaded"] = True

                if module_name in loaded_modules:
                    plugin_info["in_use"] = True

            result.append(LoadedPlugin(**plugin_info))

        for project_name, (version, module_name) in installed_plugins.items():
            if project_name in found_installed_plugins:
                continue

            plugin_info = {
                "pk": project_name,
                "filename": None,
                "name": project_name,
                "version": version,
                "keywords": [],
                "description": None,
                "installed_version": None,
                "loaded": False,
                "orphaned": True,
                "in_use": False,
            }

            if module_name in settings.INSTALLED_APPS:
                plugin_info["loaded"] = True

            if module_name in loaded_modules:
                plugin_info["in_use"] = True

            result.append(LoadedPlugin(**plugin_info))

        return result

    def get_plugin(self, pk):
        plugins = self.get_installed_plugins()
        for plugin in plugins:
            if plugin.pk == pk:
                return plugin
        return None

    def retrieve(self, request, pk=None):
        plugin = self.get_plugin()
        if plugin:
            serializer = self.serializer_class(
                plugin, context={"request": request, "view": self}
            )
            return Response(serializer.data)
        else:
            return Response({}, status=status.HTTP_404_NOT_FOUND)

    @action(methods=["post"], detail=True)
    def uninstall(self, request, pk=None):
        plugin = self.get_plugin(pk)
        if not plugin:
            return Response(
                {"status": "error", "message": "Plugin not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if plugin.in_use:
            return Response(
                {"status": "error", "message": "Plugin currently in use"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        subprocess.check_call(
            [sys.executable, "-m", "pip", "uninstall", "-y", "--verbose", plugin.pk]
        )
        if not plugin.orphaned and plugin.filename:
            p = Path(settings.PACKAGE_ROOT) / plugin.filename
            p.unlink()
        return Response({"status": "success", "message": "Plugin uninstalled"})

    def list(self, request):
        plugins = self.get_installed_plugins()
        serializer = self.serializer_class(
            plugins, many=True, context={"request": request, "view": self}
        )
        return Response(serializer.data)
