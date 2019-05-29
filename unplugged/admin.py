from django.contrib import admin

from .models import Plugin, SimpleAdminTemplate, SimpleAdminPlugin, Schedule

admin.site.register(Plugin)
admin.site.register(Schedule)
admin.site.register(SimpleAdminTemplate)
admin.site.register(SimpleAdminPlugin)
