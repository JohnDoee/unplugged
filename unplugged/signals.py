import django.dispatch

plugin_loaded = django.dispatch.Signal(providing_args=["plugin"])
plugin_unloaded = django.dispatch.Signal(providing_args=["plugin"])

wamp_realm_created = django.dispatch.Signal()
wamp_realm_discarded = django.dispatch.Signal()
