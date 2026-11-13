from pydantic import Field

from app.schemas.base import CamelModel


class ProductCategoryOut(CamelModel):
    id: int
    name: str
    sort_order: int


class ProductCategoryUpsert(CamelModel):
    name: str = Field(min_length=1, max_length=100)
