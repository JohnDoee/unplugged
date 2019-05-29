from marshmallow import SchemaOpts, fields, Schema as OriginalSchema


class UISchemaOpts(SchemaOpts):
    def __init__(self, meta, **kwargs):
        SchemaOpts.__init__(self, meta, **kwargs)
        self.ui_schema = getattr(meta, 'ui_schema', {})


class Schema(OriginalSchema):
    OPTIONS_CLASS = UISchemaOpts
