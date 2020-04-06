import copy
import logging

from django.conf.urls import url
from rest_framework import routers

from ...pluginhandler import pluginhandler
from ...plugins import ServicePlugin
from ...schema import Schema
from .models import SimpleAdminPlugin, SimpleAdminTemplate
from .views import (
    ExternalPluginModelView,
    LoadedPluginView,
    LogModelView,
    PermissionModelView,
    PluginBaseListView,
    PluginModelView,
    ScheduleModelView,
    ShowAdminUrlsView,
    SimpleAdminPluginModelView,
    SimpleAdminTemplateModelView,
    UserModelView,
)

logger = logging.getLogger(__name__)


def register_simpleadmin_template(plugin_base, template):
    if template == True:
        description = "Default template for plugin"
        display_name = "Default"
        template_id = "default"
        simpleadmin_template = True
        modify_key = None
        update_method = SimpleAdminTemplate.UPDATE_METHOD_FULL
    else:
        description = template.get("description", "No description found")
        template_id = template["id"]
        display_name = template.get("display_name", template_id)
        simpleadmin_template = template["template"]
        update_method = template["update_method"]
        modify_key = template.get("modify_key")

    if update_method == SimpleAdminTemplate.UPDATE_METHOD_MODIFY_KEY and not modify_key:
        logger.warning(f"Bogus template {template_id}")
        return

    try:
        sat = SimpleAdminTemplate.objects.get(
            template_id=template_id,
            plugin_type=plugin_base.plugin_type,
            plugin_name=plugin_base.plugin_name,
        )
    except SimpleAdminTemplate.DoesNotExist:
        sat = SimpleAdminTemplate(
            template_id=template_id,
            plugin_type=plugin_base.plugin_type,
            plugin_name=plugin_base.plugin_name,
            automatic_created=True,
        )

    logger.debug(
        f"Registering template {plugin_base.plugin_type}/{plugin_base.plugin_name}/{template_id}"
    )

    sat.description = description
    sat.display_name = display_name
    sat.template = simpleadmin_template
    sat.update_method = update_method
    sat.modify_key = modify_key

    sat.save()

    return template_id


def scan_and_register_simpleadmin_template():
    existing_templates = {
        (sat.plugin_type, sat.plugin_name, sat.template_id): sat
        for sat in SimpleAdminTemplate.objects.filter(automatic_created=True)
    }

    for plugin_base in pluginhandler.get_all_plugins():
        if not hasattr(plugin_base, "simpleadmin_templates"):
            continue

        templates = plugin_base.simpleadmin_templates
        if templates == True:
            template_id = register_simpleadmin_template(plugin_base, templates)
            key = (plugin_base.plugin_type, plugin_base.plugin_name, template_id)
            existing_templates.pop(key, None)
        else:
            for template in templates:
                template_id = register_simpleadmin_template(plugin_base, template)
                key = (plugin_base.plugin_type, plugin_base.plugin_name, template_id)
                existing_templates.pop(key, None)

    for existing_template in existing_templates.values():
        logger.debug(
            f"It seems like {existing_template} is redundant, lets delete it if it is not in use"
        )
        if SimpleAdminPlugin.objects.filter(template=existing_template).exists():
            logger.debug(f"Template {existing_template} is in use, skipping")
            continue

        existing_template.delete()


class ServiceSimpleRouter(routers.SimpleRouter):
    def __init__(self, *args, **kwargs):
        self.service = kwargs.pop("service")
        super(ServiceSimpleRouter, self).__init__(*args, **kwargs)

    @property
    def routes(self):
        r = []
        for route in routers.SimpleRouter.routes:
            route = copy.copy(route)
            route.initkwargs["service"] = self.service
            r.append(route)
        return r


class AdminService(ServicePlugin):
    plugin_name = "admin"
    config_schema = Schema

    def __init__(self, config):
        scan_and_register_simpleadmin_template()
        super(AdminService, self).__init__(config)

    def get_urls(self):
        router = ServiceSimpleRouter(service=self)

        router.register("logs", LogModelView, basename="log")

        router.register("permissions", PermissionModelView, basename="permission")
        router.register("users", UserModelView, basename="user")
        router.register("plugins", PluginModelView, basename="plugin")
        router.register("pluginbases", PluginBaseListView, basename="pluginbase")
        router.register(
            "simpleadminplugins",
            SimpleAdminPluginModelView,
            basename="simpleadmin_plugin",
        )
        router.register(
            "simpleadmintemplates",
            SimpleAdminTemplateModelView,
            basename="simpleadmin_template",
        )

        router.register("schedules", ScheduleModelView)

        router.register(
            "externalplugins", ExternalPluginModelView, basename="externalplugin"
        )
        router.register("loadedplugins", LoadedPluginView, basename="loadedplugin")

        return [
            url("^$", ShowAdminUrlsView.as_view(urls=router.urls, service=self))
        ] + router.urls

    def unload(self):
        pass
