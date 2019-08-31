from pkg_resources import get_distribution

from .base import JSONSchema

__version__ = get_distribution("marshmallow-jsonschema").version
__license__ = "MIT"


__all__ = ("JSONSchema",)
