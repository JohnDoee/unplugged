import copy
import logging

from django.conf.urls import url

from rest_framework import routers

from marshmallow import Schema

from ...plugins import ServicePlugin
from ...pluginhandler import pluginhandler

from .models import SimpleAdminTemplate, SimpleAdminPlugin
from .views import (
    PermissionModelView,
    PluginModelView,
    PluginBaseListView,
    UserModelView,
    ShowAdminUrlsView,
    SimpleAdminPluginModelView,
    SimpleAdminTemplateModelView,
    LogModelView,
    ScheduleModelView,
)

logger = logging.getLogger(__name__)


def register_simpleadmin_template(plugin_base, template):
    if template == True:
        description = "Default template for plugin"
        display_name = "Default"
        template_id = "default"
        simpleadmin_template = True
        update_method = SimpleAdminTemplate.UPDATE_METHOD_FULL
    else:
        description = template.get("description", "No description found")
        template_id = template["id"]
        display_name = template.get("display_name", f"Template {template_id}")
        simpleadmin_template = template["template"]
        update_method = template["update_method"]

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

        router.register("logs", LogModelView, base_name="log")

        router.register("permissions", PermissionModelView, base_name="permission")
        router.register("users", UserModelView, base_name="user")
        router.register("plugins", PluginModelView, base_name="plugin")
        router.register("pluginbases", PluginBaseListView, base_name="pluginbase")
        router.register(
            "simpleadminplugins",
            SimpleAdminPluginModelView,
            base_name="simpleadmin_plugin",
        )
        router.register(
            "simpleadmintemplates",
            SimpleAdminTemplateModelView,
            base_name="simpleadmin_template",
        )

        router.register("schedules", ScheduleModelView)

        return [
            url("^$", ShowAdminUrlsView.as_view(urls=router.urls, service=self))
        ] + router.urls

    def unload(self):
        pass
