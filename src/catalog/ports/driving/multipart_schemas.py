"""
Multipart/form-data input schemas for product create/update.

APIFlask's @bp.input(..., location="form_and_files") requires marshmallow-style
Schema with apiflask.fields.File so OpenAPI generates requestBody with
multipart/form-data content. The HTTP handlers still read request.form and
request.files directly — these schemas exist purely to document the wire
contract for Swagger UI consumers (frontend).
"""
from apiflask import Schema
from apiflask import fields
from apiflask.validators import Length, Range


class ProductCreateMultipartIn(Schema):
    title = fields.String(
        required=True,
        validate=Length(min=1, max=200),
        metadata={"description": "Название товара."},
    )
    price = fields.Float(
        required=True,
        validate=Range(min=0),
        metadata={"description": "Цена в рублях. Десятичный разделитель — точка."},
    )
    description = fields.String(
        load_default="",
        metadata={"description": "Описание товара. Может быть пустым."},
    )
    category_id = fields.String(
        load_default="",
        metadata={
            "description": (
                "ID категории. Пустая строка означает «без категории»."
            )
        },
    )
    tag_ids = fields.List(
        fields.String(),
        load_default=list,
        metadata={
            "description": (
                "ID тегов. Можно передать несколько повторов поля или один "
                "элемент со значениями через запятую."
            )
        },
    )
    attribute_values = fields.String(
        load_default="",
        metadata={
            "description": (
                "JSON-объект со значениями атрибутов товара, например "
                '{"color": "red", "size": "L"}. Альтернатива — отдельные '
                "поля с префиксом attr., например attr.color=red."
            )
        },
    )
    images = fields.List(
        fields.File(),
        load_default=list,
        metadata={
            "description": (
                "Файлы изображений товара. Поле повторяется по одному файлу."
            )
        },
    )


class ProductUpdateMultipartIn(Schema):
    title = fields.String(
        validate=Length(min=1, max=200),
        metadata={"description": "Новое название (опционально)."},
    )
    price = fields.Float(
        validate=Range(min=0),
        metadata={"description": "Новая цена (опционально)."},
    )
    description = fields.String(
        metadata={"description": "Новое описание (опционально)."},
    )
    category_id = fields.String(
        metadata={
            "description": (
                "ID категории. Пустая строка убирает категорию."
            )
        },
    )
    tag_ids = fields.List(
        fields.String(),
        metadata={"description": "Полный новый список ID тегов."},
    )
    attribute_values = fields.String(
        metadata={"description": "JSON со значениями атрибутов товара."},
    )
    new_images = fields.List(
        fields.File(),
        load_default=list,
        metadata={"description": "Новые файлы изображений для добавления."},
    )
    deleted_images = fields.List(
        fields.String(),
        load_default=list,
        metadata={
            "description": (
                "Пути изображений, которые нужно удалить. Передавать так, "
                "как они возвращены в ProductDetailOut.images."
            )
        },
    )
