from django.contrib import admin

from .models import SimpleAdminTemplate, SimpleAdminPlugin

admin.site.register(SimpleAdminTemplate)
admin.site.register(SimpleAdminPlugin)
