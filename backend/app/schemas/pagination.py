"""Shared shapes for paginated list endpoints (docs/API_CONVENTIONS.md, "Pagination").

    ?page=1&page_size=20   ->   {"items": [...], "page": 1, "page_size": 20, "total": 57}

A list endpoint's query schema subclasses PageArgsSchema (adding its filters); its
response schema subclasses PageSchema and adds `items`. The service pages the query
with `db.paginate(stmt, page=page, per_page=page_size, error_out=False)`.
"""

from marshmallow import Schema, fields, validate

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


class PageArgsSchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(
        load_default=PAGE_SIZE_DEFAULT, validate=validate.Range(1, PAGE_SIZE_MAX)
    )


class PageSchema(Schema):
    page = fields.Integer(required=True)
    page_size = fields.Integer(required=True)
    total = fields.Integer(required=True, metadata={"description": "Items across all pages"})
