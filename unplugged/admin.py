from django.contrib import admin

from .models import (
    Plugin,
    Schedule,
    Log,
    LogMessage,
)  # SimpleAdminPlugin, SimpleAdminTemplate,

admin.site.register(Plugin)
admin.site.register(Schedule)
# admin.site.register(SimpleAdminTemplate)
# admin.site.register(SimpleAdminPlugin)
admin.site.register(Log)
admin.site.register(LogMessage)
