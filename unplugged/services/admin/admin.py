from django.contrib import admin

from .models import ExternalPlugin, SimpleAdminPlugin, SimpleAdminTemplate

admin.site.register(ExternalPlugin)
admin.site.register(SimpleAdminTemplate)
admin.site.register(SimpleAdminPlugin)
