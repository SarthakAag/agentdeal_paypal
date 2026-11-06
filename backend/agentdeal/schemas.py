from typing import Literal, Optional
from pydantic import BaseModel, Field

Role = Literal["buyer", "seller"]


class Limits(BaseModel):
    """One side's private constraints.

    buyer : price_limit = max they pay,   delivery_limit = latest days OK
    seller: price_limit = min they accept, delivery_limit = fastest days possible
    ideal_* = what that side would love to get.
    """
    role: Role
    price_limit: float
    ideal_price: float
    delivery_limit: int
    ideal_delivery: int
    max_rounds: int = 8


class Scenario(BaseModel):
    product: str
    buyer: Limits
    seller: Limits


class Action(BaseModel):
    action: Literal["offer", "accept", "reject"]
    price: Optional[float] = None
    delivery_days: Optional[int] = None
    message: str = ""


class NegotiationResult(BaseModel):
    product: str
    status: Literal["agreed", "no_deal"]
    agreed_price: Optional[float] = None
    agreed_days: Optional[int] = None
    rounds: int
    violations: int = 0
    transcript: list[dict] = Field(default_factory=list)