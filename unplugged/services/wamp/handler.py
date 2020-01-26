import logging

from wampyre.transports.django import WAMPRouter

from ...plugins import ServicePlugin
from ...schema import Schema

logger = logging.getLogger(__name__)


class WAMPServicePlugin(ServicePlugin):
    plugin_name = "wamp"
    config_schema = Schema

    def get_channels(self):
        return [
            (
                "",
                WAMPRouter,
                {
                    "realm_authenticator": self.realm_authenticator,
                    "guard": self.wamp_guard,
                },
            )
        ]

    def realm_authenticator(user, realm):
        if not user or not user.is_authenticated():
            logger.info(f"User not authenticated for realm {realm}")
            return False

        if realm != "unplugged":
            logger.info(f"Someone tried to connect to realm {realm}")
            return False

        return True

    def wamp_guard(user, method, uri):
        if not user:
            return False

        if uri.startswith("user."):
            if user.is_staff:
                return True

            user_id = uri.split(".")[1]

            if str(user.pk) == user_id:
                return True

            return False
        elif uri.startswith("plugin."):
            uri = uri.split(".")
            if len(uri) < 3:
                return False

            plugin_type, name = uri.split(".")[1:3]
            if user.has_perm(f"unplugged.{plugin_type}.{name}"):
                return True

        return False
