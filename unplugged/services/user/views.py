import logging

from django.contrib.auth import authenticate, get_user_model, login, logout
from rest_framework import permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from ...jsonapi import JSONAPIObject, JSONAPIRoot

logger = logging.getLogger(__name__)


class AuthSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1, max_length=100)
    password = serializers.CharField(min_length=1, max_length=100)


class AuthView(APIView):
    service = None
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = AuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        UserModel = get_user_model()

        user = authenticate(
            username=serializer.data["username"], password=serializer.data["password"]
        )

        if user is not None:
            if user.is_active:
                logger.info("User %r logged in successfully" % (user,))
                login(request, user)
                return Response(
                    {"status": "success", "message": "logged in successfully"}
                )
            else:
                logger.info("User %r tried to login but is not active" % (user,))
                return Response({"status": "error", "message": "not authenticated"})
        elif not UserModel.objects.all().exists():
            logger.info("Creating new user as none exist")
            user = UserModel.objects.create_superuser(
                username=serializer.data["username"],
                password=serializer.data["password"],
                email=None,
            )
            login(request, user)
            return Response(
                {"status": "success", "message": "Created new user and logged in"}
            )
        else:
            logger.info("Login failed for username %s" % (serializer.data["username"],))
            return Response({"status": "error", "message": "not authenticated"})


class UserView(APIView):
    service = None
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        obj = JSONAPIObject("userinfo", request.user.username)

        obj["is_authenticated"] = bool(request.user.is_authenticated)

        if request.user.is_authenticated:
            obj["username"] = request.user.username
            obj["token"] = Token.objects.get_or_create(user=request.user)[0].key

        obj.links = {
            "self": request.build_absolute_uri("/%s/" % (self.service.name,)),
            "auth": request.build_absolute_uri("/%s/%s" % (self.service.name, "auth")),
            "logout": request.build_absolute_uri(
                "/%s/%s" % (self.service.name, "logout")
            ),
        }

        root = JSONAPIRoot()
        root.append(obj)

        return Response(root.serialize(request))


class LogoutView(APIView):
    service = None
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        logout(request)
        return Response({"status": "success"})
