import logging
import re

logger = logging.getLogger(__name__)


def register_urlpatterns(urls):
    logger.debug("Registering urls: %r" % (urls,))
    urlpatterns.extend(urls)


def unregister_urlpattern(pattern):
    logger.debug("Unregistering pattern: %s" % (pattern,))
    pattern = re.compile(pattern)
    for i, p in enumerate(urlpatterns):
        if pattern == p.pattern.regex:
            break
    else:
        return

    urlpatterns.pop(i)


def clear_urlpatterns():
    logger.debug("Clearing url patterns")
    urlpatterns[:] = []


urlpatterns = []
