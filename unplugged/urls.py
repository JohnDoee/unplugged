from django.conf.urls import url

from rest_framework import routers

from .views import PluginModelView, PluginBaseListView, SimpleAdminPluginModelView, SimpleAdminTemplateModelView, \
                   ShowAdminUrlsView, ScheduleModelView

router = routers.SimpleRouter()

router.register(r'plugins', PluginModelView)
router.register(r'pluginbases', PluginBaseListView, base_name='pluginbase')
router.register(r'simpleadminplugins', SimpleAdminPluginModelView, base_name='simpleadmin_plugin')
router.register(r'simpleadmintemplates', SimpleAdminTemplateModelView, base_name='simpleadmin_template')

router.register(r'schedules', ScheduleModelView)

urlpatterns = [
    url(r'^$', ShowAdminUrlsView.as_view(urls=router.urls)),
] + router.urls
