"""
Schemas for customer keyword documents.
"""
from typing import Optional

from pydantic import BaseModel, Field


class CustomerKeyword(BaseModel):
    customerCd: int = Field(alias="customer_cd")
    customerName: Optional[str] = Field(default=None, alias="customer_name")
    keywords: list[str]

    class Config:
        populate_by_name = True
