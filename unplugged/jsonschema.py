from .schema import fields


def dump_ui_schema(obj):
    ui_schema = {}
    ui_schema.update(getattr(obj.opts, "ui_schema", {}))
    for field_name, field in sorted(obj.fields.items()):
        if isinstance(field, fields.Nested):
            nested_ui_schema = dump_ui_schema(field.nested())
            if field.many:
                nested_ui_schema = {"items": nested_ui_schema}
            field_ui_schema = nested_ui_schema
        else:
            field_ui_schema = field.metadata.get("ui_schema")

        if field_ui_schema:
            ui_schema[field_name] = field_ui_schema

    return ui_schema
