from django.contrib import admin

from .models import SimpleAdminPlugin, SimpleAdminTemplate

admin.site.register(SimpleAdminTemplate)
admin.site.register(SimpleAdminPlugin)
