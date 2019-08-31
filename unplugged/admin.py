from django.contrib import admin

from .models import Log, LogMessage, Plugin, Schedule

admin.site.register(Plugin)
admin.site.register(Schedule)
admin.site.register(Log)
admin.site.register(LogMessage)
