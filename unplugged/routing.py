import logging
import re

logger = logging.getLogger(__name__)


def register_channels(channels):
    logger.debug("Registering channels: %r" % (channels,))
    urlpatterns.extend(channels)


def unregister_channel(pattern):
    logger.debug("Unregistering pattern: %s" % (pattern,))
    pattern = re.compile(pattern)
    for i, p in enumerate(urlpatterns):
        if pattern == p.pattern.regex:
            break
    else:
        return

    urlpatterns.pop(i)


def clear_channels():
    logger.debug("Clearing channels")
    urlpatterns[:] = []


urlpatterns = []
