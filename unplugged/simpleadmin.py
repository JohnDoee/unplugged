import logging

from .models import SimpleAdminTemplate, SimpleAdminPlugin
from .pluginhandler import pluginhandler

logger = logging.getLogger(__name__)


def register_simpleadmin_template(plugin_base, template):
    if template == True:
        description = 'Default template for plugin'
        display_name = 'Default'
        template_id = 'default'
        simpleadmin_template = True
        update_method = SimpleAdminTemplate.UPDATE_METHOD_FULL
    else:
        description = template.get('description', 'No description found')
        template_id = template['id']
        display_name = template.get('display_name', 'Template %s' % (template_id, ))
        simpleadmin_template = template['template']
        update_method = template['update_method']

    try:
        sat = SimpleAdminTemplate.objects.get(template_id=template_id, plugin_type=plugin_base.plugin_type, plugin_name=plugin_base.plugin_name)
    except SimpleAdminTemplate.DoesNotExist:
        sat = SimpleAdminTemplate(template_id=template_id, plugin_type=plugin_base.plugin_type, plugin_name=plugin_base.plugin_name, automatic_created=True)

    logger.debug('Registering template %s/%s/%s' % (plugin_base.plugin_type, plugin_base.plugin_name, template_id, ))

    sat.description = description
    sat.display_name = display_name
    sat.template = simpleadmin_template
    sat.update_method = update_method

    sat.save()

    return template_id


def scan_and_register_simpleadmin_template():
    existing_templates = {(sat.plugin_type, sat.plugin_name, sat.template_id): sat for sat in SimpleAdminTemplate.objects.filter(automatic_created=True)}

    for plugin_base in pluginhandler.get_all_plugins():
        if not hasattr(plugin_base, 'simpleadmin_templates'):
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
        logger.debug('It seems like %s is redundant, lets delete it if it is not in use' % (existing_template, ))
        if SimpleAdminPlugin.objects.filter(template=existing_template).exists():
            logger.debug('Template %s is in use, skipping' % (existing_template, ))
            continue

        existing_template.delete()
