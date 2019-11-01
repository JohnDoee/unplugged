import logging

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import Plugin

logger = logging.getLogger(__name__)


class StaticUrlsView(APIView):
    service = None

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(self.service.plugin_url_root.serialize(request))
