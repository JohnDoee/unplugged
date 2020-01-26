import inspect
import logging
from functools import wraps

from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.response import Response

from .jsonapi import JSONAPIObject, JSONAPIRoot
from .jsonschema import dump_ui_schema
from .libs.marshmallow_jsonschema import JSONSchema
from .schema import INCLUDE, Schema, ValidationError

logger = logging.getLogger(__name__)


class CommandViewMixin:
    def call_command(self, request, obj, additional_kwargs=None):
        additional_kwargs = additional_kwargs or {}
        serializer = CommandSerializer(data=request.data)
        if not serializer.is_valid():
            jsonapi_root = JSONAPIRoot.error_status(
                id_="deserialize_failed", detail="Failed to deserialize your request"
            )
            jsonapi_root.meta.update(serializer.errors)
            return Response(
                jsonapi_root.serialize(request), status=status.HTTP_400_BAD_REQUEST
            )

        command_name = serializer.validated_data["name"]
        command = obj.get_command(command_name)
        if not command:
            jsonapi_root = JSONAPIRoot.error_status(
                id_="unknown_command", detail=f"{command_name} is not a known command"
            )
            jsonapi_root.meta.update(serializer.errors)
            return Response(
                jsonapi_root.serialize(request), status=status.HTTP_400_BAD_REQUEST
            )

        kwargs = serializer.validated_data["kwargs"]
        try:
            kwargs = command.parse_kwargs(kwargs)
        except ValidationError as err:
            jsonapi_root = JSONAPIRoot.error_status(
                id_="invalid_args",
                detail=f"You provided invalid arguments to the function {command}",
            )
            jsonapi_root.meta.update(err.messages)
            return Response(
                jsonapi_root.serialize(request), status=status.HTTP_400_BAD_REQUEST
            )

        kwargs["self"] = obj
        kwargs.update(additional_kwargs)
        if command.need_request:
            kwargs["request"] = request

        try:
            command_result = command.execute(kwargs)
        except Exception:
            logger.exception(f"Failed to execute {command} with args {kwargs}")
            jsonapi_root = JSONAPIRoot.error_status(
                id_="execution_failed", detail="Failed to execute command"
            )
            return Response(
                jsonapi_root.serialize(request), status=status.HTTP_400_BAD_REQUEST
            )

        if isinstance(command_result, HttpResponse):
            return command_result

        if isinstance(command_result, JSONAPIRoot):
            return Response(command_result.serialize(request))

        jsonapi_root = JSONAPIRoot.success_status(command_result)
        return Response(jsonapi_root.serialize(request))


class CommandBase:
    @classmethod
    def get_jsonapi_commands(cls):
        commands = getattr(cls, "__commands__", None) or {}
        serialized_commands = []
        for command_obj, command in zip(
            CommandSerializer(commands.values(), many=True).data, commands.values()
        ):
            obj = JSONAPIObject("command", command.name, command)
            obj.update(command_obj)
            serialized_commands.append(obj)
        return serialized_commands

    def get_command(self, command):
        return self.__commands__.get(command)


class CommandBaseMeta(type):
    def __new__(mcls, name, bases, namespace):
        if CommandBase not in bases:
            bases += (CommandBase,)
        cls = super(CommandBaseMeta, mcls).__new__(mcls, name, bases, namespace)
        cls.__commands__ = {}
        for fn_name, fn in inspect.getmembers(cls, predicate=inspect.isfunction):
            command = getattr(fn, "__command__", None)
            if command:
                cls.__commands__[command.name] = command

        return cls


class Command:
    def __init__(
        self,
        fn,
        name=None,
        display_name=None,
        description=None,
        schema=None,
        metadata=None,
        need_request=False,
    ):
        self.fn = fn
        if name:
            self.name = name
        else:
            if fn.__name__.startswith("command_"):
                self.name = fn.__name__[8:]
            else:
                self.name = fn.__name__

        self.display_name = display_name or self.name
        self.description = description or "No description found"
        self.schema = schema or Schema
        self.metadata = metadata or {}
        self.need_request = need_request

    def parse_kwargs(self, kwargs):
        return self.schema().load(kwargs, unknown=INCLUDE)

    def execute(self, kwargs):
        try:
            result = self.fn(**kwargs)
        except:
            raise
        else:
            return result


def command(
    name=None,
    display_name=None,
    description=None,
    schema=None,
    metadata=None,
    need_request=False,
):
    def decorator(fn):
        fn.__command__ = Command(
            fn, name, display_name, description, schema, metadata, need_request
        )

        @wraps(fn)
        def decorated(*args, **kwargs):
            return fn(*args, **kwargs)

        return decorated

    return decorator


class CommandSerializer(serializers.Serializer):
    command = serializers.CharField(source="name")
    kwargs = serializers.DictField(required=False, write_only=True)
    display_name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    schema = serializers.SerializerMethodField(read_only=True)
    ui_schema = serializers.SerializerMethodField(read_only=True)

    def get_schema(self, obj):
        schema = obj.schema()
        json_schema = JSONSchema()
        return json_schema.dump(schema)

    def get_ui_schema(self, obj):
        schema = obj.schema()
        return dump_ui_schema(schema)
