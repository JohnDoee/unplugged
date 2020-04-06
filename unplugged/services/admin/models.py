import copy
import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from jsonfield import JSONField

from ...baseplugin import RelatedPluginField
from ...models import Plugin
from ...pluginhandler import pluginhandler
from ...schema import Schema, fields

logger = logging.getLogger(__name__)


class NameAlreadyInUseException(Exception):
    pass


def key_name_in_use(plugin, modify_key, name):
    names = set([item["name"] for item in plugin.config.get(modify_key, [])])
    return name in names or slugify(name) in names


class SimpleAdminTemplate(models.Model):
    display_name = models.CharField(max_length=200)
    description = models.TextField(default="No description found")
    template_id = models.CharField(max_length=100)
    plugin_type = models.CharField(max_length=100)
    plugin_name = models.CharField(max_length=100)
    modify_key = models.CharField(max_length=40, null=True, blank=True)
    template = JSONField()

    UPDATE_METHOD_FULL = "full"
    UPDATE_METHOD_MODIFY_KEY = "modify_key"
    UPDATE_METHOD_CHOICES = (
        (UPDATE_METHOD_FULL, "Full"),
        (UPDATE_METHOD_MODIFY_KEY, "Modify Key"),
    )
    update_method = models.CharField(max_length=100, choices=UPDATE_METHOD_CHOICES)
    automatic_created = models.BooleanField(default=False)

    def __str__(self):
        return f"SimpleAdminTemplate {self.display_name}"

    class Meta:
        verbose_name_plural = "Simple Admin Templates"
        unique_together = (("template_id", "plugin_type", "plugin_name"),)
        db_table = "services_admin_simpleadmin_template"

    @property
    def config_schema(self):
        plugin = pluginhandler.get_plugin(self.plugin_type, self.plugin_name)
        if not plugin:
            return Schema

        schema = plugin.config_schema
        if self.update_method == self.UPDATE_METHOD_MODIFY_KEY:
            schema = schema._declared_fields[self.modify_key].nested

        def is_userinput(template, field_key):
            return (
                isinstance(template[field_key], dict)
                and template[field_key].get("simpleAdminMethod") == "userInput"
            )

        def is_injectable(template, field_key):
            return (
                isinstance(template[field_key], dict)
                and template[field_key].get("simpleAdminMethod") == "injectablePlugin"
            )

        def create_schema(schema, template, root=False, hide_fields=None):
            schema_keys = {}
            added_fields = False

            ui_schema = {"ui:order": []}
            existing_ui_schema = getattr(schema.Meta, "ui_schema", {})

            if template == True:
                ui_schema.update(existing_ui_schema)

            ui_schema["ui:order"] = list(ui_schema["ui:order"])

            for key, field in schema._declared_fields.items():
                if template != True and key not in template:
                    continue

                if hide_fields is not None:
                    if key not in hide_fields:
                        schema_keys[key] = field
                elif template == True:
                    schema_keys[key] = field
                elif is_userinput(template, key):
                    nested_hide_fields = template[key].get("hideFields")
                    new_field = copy.copy(field)
                    if nested_hide_fields:
                        nested_schema, nested_added_fields = create_schema(
                            field.nested, True, hide_fields=nested_hide_fields
                        )
                        new_field.nested = nested_schema
                    new_field.required = template[key].get("required", field.required)
                    schema_keys[key] = new_field
                    added_fields = True
                elif isinstance(field, fields.Nested):
                    nested_schema, nested_added_fields = create_schema(
                        field.nested, template[key]
                    )
                    if nested_added_fields:
                        new_field = copy.copy(field)
                        new_field.nested = nested_schema
                        schema_keys[key] = new_field
                        added_fields = True

            if isinstance(template, dict):
                for key, template_field in template.items():
                    if is_injectable(template, key):
                        plugin_type = pluginhandler.get_plugin_type(
                            template_field["plugin_type"]
                        )
                        traits = template_field.get("traits", [])
                        schema_keys[key] = RelatedPluginField(
                            required=True, plugin_type=plugin_type, traits=traits
                        )

            if (
                root
                and self.update_method == self.UPDATE_METHOD_FULL
                and "display_name" not in schema_keys
            ):
                # schema_keys['name'] = fields.String(required=True, pattern=r'^[a-z0-9]+(?:[-_][a-z0-9]+)*$', ui_schema={'ui:title': 'Name'})
                schema_keys["display_name"] = fields.String(
                    required=True, default="", ui_schema={"ui:title": "Name"},
                )
                ui_schema["ui:order"].insert(0, "display_name")

            for field_name in schema_keys.keys():
                if field_name not in ui_schema["ui:order"]:
                    ui_schema["ui:order"].append(field_name)

            existing_ui_order = ["display_name"] + existing_ui_schema.get(
                "ui:order", []
            )

            def get_index(f):
                try:
                    return existing_ui_order.index(f)
                except ValueError:
                    return 100

            ui_schema["ui:order"].sort(key=get_index)

            if root and self.update_method == self.UPDATE_METHOD_MODIFY_KEY:
                schema_keys[self.modify_key] = RelatedPluginField(
                    required=True, plugin_name=plugin, ui_schema={"ui:title": "Items"}
                )
                ui_schema["ui:order"].append(self.modify_key)

            schema_keys["Meta"] = type("Meta", (), {"ui_schema": ui_schema})

            schema_cls = type(schema.__name__, (Schema,), schema_keys)
            if root:
                return schema_cls
            else:
                return schema_cls, added_fields

        return create_schema(schema, self.template, root=True)

    def add_plugin(self, name, items=None):
        if self.update_method == self.UPDATE_METHOD_FULL:
            try:
                Plugin.objects.get(plugin_type=self.plugin_type, name=name)
                raise NameAlreadyInUseException(f"Name {name} is already used")
            except Plugin.DoesNotExist:
                plugin = Plugin.objects.create(
                    plugin_type=self.plugin_type,
                    plugin_name=self.plugin_name,
                    name=name,
                    enabled=True,
                )
        elif self.update_method == self.UPDATE_METHOD_MODIFY_KEY:
            plugins = Plugin.objects.filter(
                plugin_type=self.plugin_type, plugin_name=self.plugin_name
            ).order_by("id")

            if items:
                plugins = plugins.filter(pk=items)

            if not plugins:
                return None

            enabled_plugins = plugins.filter(enabled=True)

            if enabled_plugins:
                plugin = enabled_plugins[0]
            else:
                plugin = plugins[0]

            if key_name_in_use(plugin, self.modify_key, name):
                raise NameAlreadyInUseException(f"Name {name} is already used")
        else:
            raise Exception(f"Unknown update method {self.update_method}")

        sap = SimpleAdminPlugin.objects.create(template=self, name=name, plugin=plugin)

        return sap

    def get_injectable_plugin_fields(self):
        fields = []
        if isinstance(self.template, dict):
            for k, v in self.template.items():
                if not isinstance(v, dict):
                    continue

                if v.get("simpleAdminMethod") == "injectablePlugin":
                    fields.append(k)

        return fields


class SimpleAdminPlugin(models.Model):
    template = models.ForeignKey(SimpleAdminTemplate, on_delete=models.deletion.CASCADE)
    plugin = models.ForeignKey(Plugin, on_delete=models.deletion.CASCADE)
    auto_created_plugins = models.ManyToManyField(
        Plugin, related_name="auto_created_plugins", blank=True
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Slugified name, used for actual name (and be able to find the plugin again)",
    )
    display_name = models.CharField(
        max_length=200, blank=True, null=True, help_text="Human readable name"
    )
    config = JSONField(default=dict, blank=True)
    priority = models.SmallIntegerField(default=1)

    class Meta:
        verbose_name_plural = "Simple Admin Plugin"
        db_table = "services_admin_simpleadmin_plugin"
        ordering = ["priority"]

    def delete_plugin(self):
        for auto_created_plugin in self.auto_created_plugins.all():
            logger.debug(
                "Deleting auto-created plugin %r from %r"
                % (auto_created_plugin, self.plugin)
            )
            auto_created_plugin.remove_plugin()
            auto_created_plugin.delete()

        if self.template.update_method == self.template.UPDATE_METHOD_FULL:
            logger.debug(f"Removing plugin {self.plugin} completely with plugin {self}")
            self.plugin.remove_plugin()
            self.plugin.delete()
        elif self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
            logger.debug(f"Removing a key plugin from {self.plugin} with plugin {self}")
            found_item = False
            for i, item in enumerate(
                self.plugin.config.get(self.template.modify_key, [])
            ):
                if (
                    item["name"] == self.name
                    or item.get("_simpleadminplugin_id") == self.pk
                ):
                    found_item = True
                    break

            if found_item:
                self.plugin.config[self.template.modify_key].pop(i)
                self.plugin.save()

    def check_in_use_by(self):
        if self.plugin.is_plugin_loaded():
            plugin_obj = self.plugin.get_plugin()
            return plugin_obj._related_plugins

        return []

    def reload_plugin(self):
        self.plugin.reload_plugin()

    def update_plugin(
        self, form_data
    ):  # TODO: maybe make it choose a new name if already in use?
        """
        Update the actual plugin with the new form_data.
        """
        filled_form_data = self.fill_form_data(form_data)
        filled_form_data["_simpleadminplugin_id"] = self.pk
        name = form_data.get("name") or filled_form_data.get("name") or self.name
        display_name = (
            form_data.get("display_name")
            or filled_form_data.get("display_name")
            or self.display_name
        )
        assert name

        if name != self.name:
            if self.template.update_method == self.template.UPDATE_METHOD_FULL:
                try:
                    Plugin.objects.get(plugin_type=self.plugin.plugin_type, name=name)
                    raise NameAlreadyInUseException(
                        f"Unable to rename because name {name} is already used"
                    )
                except Plugin.DoesNotExist:
                    pass
            elif self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
                if key_name_in_use(self.plugin, self.template.modify_key, name):
                    raise NameAlreadyInUseException(
                        f"Unable to save because name {name} is already used"
                    )

        plugin_cls = pluginhandler.get_plugin(
            self.template.plugin_type, self.template.plugin_name
        )
        schema = plugin_cls.config_schema
        if self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
            schema = schema._declared_fields[self.template.modify_key].nested
        filled_form_data.update(schema().dump(filled_form_data))

        should_reload = False
        if self.template.update_method == self.template.UPDATE_METHOD_FULL:
            logger.debug(f"Doing a full fill of form data to {self.plugin} from {self}")
            self.plugin.config = filled_form_data
            self.plugin.name = name
            should_reload = True
        elif self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
            logger.debug(
                f"Doing a partial fill of form data to {self.plugin} from {self}"
            )

            if self.plugin.config.get(self.template.modify_key):
                updated_item = False
                for item in self.plugin.config[self.template.modify_key]:
                    if (
                        item["name"] == self.name
                        or item.get("_simpleadminplugin_id") == self.pk
                    ):
                        item.clear()
                        item.update(filled_form_data)
                        updated_item = True
                        break

                if not updated_item:
                    self.plugin.config[self.template.modify_key].append(
                        filled_form_data
                    )
            else:
                self.plugin.config[self.template.modify_key] = [filled_form_data]

        for key in self.template.get_injectable_plugin_fields():
            if key in form_data:
                self.config[key] = form_data[key]

        self.plugin.enabled = True
        self.plugin.save()

        if should_reload:
            self.reload_plugin()

        self.name = name
        if display_name:
            self.display_name = display_name

    def fill_form_data(self, form_data):
        """
        Fills the partial form with auto-completed fields from the template.
        """

        def create_plugin(template):
            if self.pk is not None:
                # full_name = '%s_%s' % (self.pk, template['name'])
                # vars = {'name': full_name, 'id': self.pk}
                name = template["name"] % {"name": self.pk}
                config = {
                    k: v % {"name": self.pk}
                    for (k, v) in template.get("config", {}).items()
                }
                plugin, created = Plugin.objects.get_or_create(
                    name=name,
                    plugin_type=template["plugin_type"],
                    plugin_name=template["plugin_name"],
                    config=config,
                    defaults={"enabled": True},
                )
                if created:
                    self.auto_created_plugins.add(plugin)
                else:
                    pass  # TODO: make sure it's not autocreated
                return plugin.pk
            else:
                return None

        injectable_plugins = {}

        def fill_data(template, source_form_data=None, key=None):
            if isinstance(template, dict):
                method = template.get("simpleAdminMethod")
                if method:
                    if method == "userInput":
                        return source_form_data
                    elif method == "lookupPlugin":
                        plugins = Plugin.objects.filter(
                            plugin_type=template["plugin_type"],
                            name=template["name"],
                            enabled=True,
                        )
                        if plugins:
                            return plugins[0].pk
                        else:
                            logger.warning(
                                f"Unable to find plugin plugin_type:{template['plugin_type']} name:{template['name']}"
                            )
                            return None
                    elif method == "lookupAllPlugins":
                        return Plugin.objects.filter(
                            plugin_type=template["plugin_type"], enabled=True
                        ).values_list("pk", flat=True)
                    elif method == "createPlugin":
                        return create_plugin(template)
                    elif method == "createPluginPriority":
                        for plugin_template in template["pluginPriorities"]:
                            if not pluginhandler.get_plugin(
                                plugin_template["plugin_type"],
                                plugin_template["plugin_name"],
                            ):
                                continue
                            return create_plugin(plugin_template)
                    elif method == "slugify":
                        return slugify(form_data[template["source"]])
                    elif method == "injectablePlugin":
                        logger.debug("We got data: %r" % (source_form_data,))
                        injectable_plugins[key] = source_form_data
                    elif method == "injectedPlugin":
                        return injectable_plugins[template["id"]]
                else:
                    retval = {}
                    for k, v in template.items():
                        if isinstance(v, list):
                            result = []
                            for vv in v:
                                filled_value = fill_data(vv, key=k)
                                if filled_value is not None:
                                    result.append(filled_value)
                            retval[k] = result
                        else:
                            source_value = None
                            if (
                                isinstance(source_form_data, dict)
                                and source_form_data.get(k) is not None
                            ):
                                source_value = source_form_data[k]

                            filled_value = fill_data(v, source_value, key=k)
                            if filled_value is not None:
                                retval[k] = filled_value

                    return retval
            else:
                return template

        if self.template.template == True:
            return form_data
        else:
            template = self.template.template
            if (
                isinstance(template, dict)
                and "name" not in template
                and "display_name" in template
            ):
                template["name"] = {
                    "simpleAdminMethod": "slugify",
                    "source": "display_name",
                }
            return fill_data(self.template.template, form_data)

    def pull_form_data(self):
        schema = self.template.config_schema
        config = dict(self.plugin.config)
        config["name"] = self.plugin.name
        if "display_name" not in config:
            config["display_name"] = self.get_display_name()

        data = {}

        if self.template.update_method == self.template.UPDATE_METHOD_FULL:
            data = schema().dump(config)
        elif self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
            for item in config.get(self.template.modify_key, []):
                if item["name"] == self.name:
                    item = dict(item)
                    item[self.template.modify_key] = self.plugin.pk
                    data = schema().dump(item)

        for key in self.template.get_injectable_plugin_fields():
            if key in self.config:
                data[key] = self.config.get(key)

        return data

    def get_display_name(self):
        config = self.plugin.config
        if self.template.update_method == self.template.UPDATE_METHOD_MODIFY_KEY:
            for item in config.get(self.template.modify_key, []):
                if item["name"] == self.name:
                    config = item
                    break
            else:
                config = {}

        return (
            self.display_name
            or config.get("display_name")
            or self.name
            or "No name found"
        )

    def __str__(self):
        return f"SimpleAdminPlugin {self.name}"


class ExternalPlugin(models.Model):
    name = models.CharField(max_length=150, null=True)
    version = models.CharField(max_length=30, null=True)
    description = models.TextField(null=True)
    keywords = JSONField(default=list, blank=True)
    plugin_file = models.FileField(upload_to="externalplugins/")

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ExternalPlugin {self.name} ({self.plugin_file.name})"

    def install(self):
        package_root = Path(settings.PACKAGE_ROOT)
        if not settings.PACKAGE_ROOT or not package_root.is_dir():
            return "Faild to install, package root does not exist"

        source = Path(self.plugin_file.path)
        destination = package_root / Path(self.plugin_file.name).name

        if destination.exists():
            return "Failed to install, plugin already installed"

        shutil.copy(source, destination)
