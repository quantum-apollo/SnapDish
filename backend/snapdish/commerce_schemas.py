"""
Pydantic models for Agentic Commerce Protocol (Instant Checkout in ChatGPT).

Align with the official spec: https://developers.openai.com/commerce/specs/checkout
Use for checkout REST request/response bodies and webhook payloads.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Item (request) ---

class Item(BaseModel):
    """Item in the cart (id from product feed + quantity)."""
    id: str = Field(..., description="Id of merchandise that can be purchased")
    quantity: int = Field(..., ge=1, description="Quantity for fulfillment")


# --- Address ---

class Address(BaseModel):
    """Fulfillment or billing address. Spec: name, line_one, city, state, country, postal_code required; line_two, phone_number optional. Max lengths: name 256, line_one/line_two/city 60, postal_code 20; state/country ISO 3166-1; phone E.164."""
    name: str = Field(..., max_length=256)
    line_one: str = Field(..., max_length=60)
    line_two: str | None = Field(None, max_length=60)
    city: str = Field(..., max_length=60)
    state: str = Field(..., description="ISO 3166-1 state/county/province/region")
    country: str = Field(..., description="ISO 3166-1 country")
    postal_code: str = Field(..., max_length=20)
    phone_number: str | None = Field(None, description="E.164 optional")


# --- Buyer ---

class Buyer(BaseModel):
    """Buyer information. Spec: name and email required; phone_number optional (E.164)."""
    name: str = Field(..., max_length=256)
    email: str = Field(..., max_length=256)
    phone_number: str | None = Field(None, description="E.164 optional")


# --- Payment provider & payment data ---

PaymentProviderName = Literal["stripe", "adyen", "braintree"]
PaymentMethod = Literal["card"]


class PaymentProvider(BaseModel):
    """Payment provider and supported methods (required on create session response)."""
    provider: PaymentProviderName = Field(...)
    supported_payment_methods: list[PaymentMethod] = Field(..., min_length=1)


class PaymentData(BaseModel):
    """Payment data for complete checkout. Token from Delegated Payment; optional billing_address."""
    token: str = Field(..., description="Payment method token from PSP")
    provider: PaymentProviderName = Field(...)
    billing_address: Address | None = None


# --- Line item & totals ---

class LineItem(BaseModel):
    """Line item with computed costs. All amounts in minor currency units. total = base_amount - discount + tax."""
    id: str = Field(..., description="Unique line item id (distinct from item id)")
    item: Item
    base_amount: int = Field(..., ge=0)
    discount: int = Field(0, ge=0)
    subtotal: int = Field(..., ge=0)
    tax: int = Field(0, ge=0)
    total: int = Field(..., ge=0)


TotalType = Literal[
    "items_base_amount", "items_discount", "subtotal", "discount",
    "fulfillment", "tax", "fee", "total"
]


class Total(BaseModel):
    """A total row. amount in minor units. Spec: validation rules for subtotal/total consistency."""
    type: TotalType = Field(...)
    display_text: str
    amount: int = Field(..., ge=0)


# --- Fulfillment options ---

class FulfillmentOptionShipping(BaseModel):
    """Shipping fulfillment option. RFC 3339 for delivery times."""
    type: Literal["shipping"] = "shipping"
    id: str
    title: str
    subtitle: str
    carrier: str
    earliest_delivery_time: str = Field(..., description="RFC 3339")
    latest_delivery_time: str = Field(..., description="RFC 3339")
    subtotal: int = Field(..., ge=0)
    tax: int = Field(0, ge=0)
    total: int = Field(..., ge=0)


class FulfillmentOptionDigital(BaseModel):
    """Digital fulfillment option."""
    type: Literal["digital"] = "digital"
    id: str
    title: str
    subtitle: str | None = None
    subtotal: int = Field(..., ge=0)
    tax: int = Field(0, ge=0)
    total: int = Field(..., ge=0)


# Union for fulfillment options (use when parsing; for building responses pick one model)
FulfillmentOption = FulfillmentOptionShipping | FulfillmentOptionDigital


# --- Messages (info vs error) ---

class MessageInfo(BaseModel):
    """Informational message. param is RFC 9535 JSONPath to the checkout component."""
    type: Literal["info"] = "info"
    param: str = Field(..., description="JSONPath e.g. $.line_items[1]")
    content_type: Literal["plain", "markdown"] = "plain"
    content: str


class MessageError(BaseModel):
    """Error message. code enum: missing, invalid, out_of_stock, payment_declined, requires_sign_in, requires_3ds."""
    type: Literal["error"] = "error"
    code: Literal["missing", "invalid", "out_of_stock", "payment_declined", "requires_sign_in", "requires_3ds"] = Field(...)
    param: str | None = Field(None, description="JSONPath if applicable")
    content_type: Literal["plain", "markdown"] = "plain"
    content: str


# --- Links ---

LinkType = Literal["terms_of_use", "privacy_policy", "seller_shop_policies"]


class Link(BaseModel):
    """Link to show to the customer."""
    type: LinkType = Field(...)
    url: str


# --- Checkout session status & response ---

CheckoutStatus = Literal["not_ready_for_payment", "ready_for_payment", "completed", "canceled"]


class Order(BaseModel):
    """Order created after completing checkout. Returned in complete response."""
    id: str = Field(..., description="Unique order id")
    checkout_session_id: str
    permalink_url: str = Field(..., description="URL for customer to view order (e.g. with email)")


class CheckoutSessionResponse(BaseModel):
    """Full checkout session state. Return on create (201), update, get, complete, cancel. Create must include payment_provider."""
    id: str
    payment_provider: PaymentProvider | None = Field(None, description="Required on create; optional on update/get")
    status: CheckoutStatus
    currency: str = Field(..., description="ISO 4217 lower case e.g. usd")
    line_items: list[LineItem]
    fulfillment_address: Address | None = None
    fulfillment_options: list[FulfillmentOptionShipping | FulfillmentOptionDigital] = Field(default_factory=list)
    fulfillment_option_id: str | None = None
    totals: list[Total]
    messages: list[MessageInfo | MessageError] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    buyer: Buyer | None = None
    order: Order | None = Field(None, description="Present on complete response when order created")


# --- Request bodies ---

class CreateCheckoutSessionRequest(BaseModel):
    """POST /checkout_sessions body."""
    buyer: Buyer | None = None
    items: list[Item] = Field(..., min_length=1)
    fulfillment_address: Address | None = None


class UpdateCheckoutSessionRequest(BaseModel):
    """POST /checkout_sessions/{id} body."""
    buyer: Buyer | None = None
    items: list[Item] | None = None
    fulfillment_address: Address | None = None
    fulfillment_option_id: str | None = None


class CompleteCheckoutSessionRequest(BaseModel):
    """POST /checkout_sessions/{id}/complete body."""
    buyer: Buyer | None = None
    payment_data: PaymentData = Field(...)


# --- Error response (4xx/5xx) ---

ErrorType = Literal["invalid_request"]
ErrorCode = Literal["request_not_idempotent"]  # spec example; extend per spec


class CheckoutErrorResponse(BaseModel):
    """Error body for 4xx/5xx responses."""
    type: ErrorType = Field(...)
    code: ErrorCode = Field(...)
    message: str = Field(..., description="Human-readable error")
    param: str | None = Field(None, description="JSONPath to offending request field")


# --- Webhooks (Merchant → OpenAI) ---

OrderStatus = Literal["created", "manual_review", "confirmed", "canceled", "shipped", "fulfilled"]
RefundType = Literal["store_credit", "original_payment"]


class Refund(BaseModel):
    """Refund issued for the order."""
    type: RefundType
    amount: int = Field(..., ge=0)


class EventDataOrder(BaseModel):
    """Order event data in webhook payload."""
    type: Literal["order"] = "order"
    checkout_session_id: str
    permalink_url: str
    status: OrderStatus
    refunds: list[Refund] = Field(default_factory=list)


WebhookEventType = Literal["order_created", "order_updated"]


class WebhookEvent(BaseModel):
    """Webhook event sent to OpenAI. Sign payload with HMAC; send in header e.g. Merchant_Name-Signature."""
    type: WebhookEventType
    data: EventDataOrder
