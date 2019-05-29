import django.dispatch


plugin_loaded = django.dispatch.Signal(providing_args=['plugin'])
plugin_unloaded = django.dispatch.Signal(providing_args=['plugin'])
