# Commerce capabilities — Agentic Commerce Protocol & Instant Checkout (ChatGPT)

SnapDish can sell through **ChatGPT** using the **Agentic Commerce Protocol**, so users can discover and buy from you inside ChatGPT while you keep the customer relationship, orders, and payments.

## What is the Agentic Commerce Protocol?

OpenAI and Stripe steward an open, community-designed protocol (Apache 2.0) so that:

- **Merchants** keep the direct customer relationship; payment flows to you; you accept/decline orders and handle post-purchase.
- **Users** can find and buy through ChatGPT (Instant Checkout) with trusted, fast recommendations.
- **Implementations** work across payment processors, platforms, and business types.

References:

- [agenticcommerce.dev](https://agenticcommerce.dev) · [GitHub](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol)
- OpenAI: [Commerce overview](https://developers.openai.com/commerce) · [Get started](https://developers.openai.com/commerce/guides/get-started) · [Key concepts](https://developers.openai.com/commerce/guides/key-concepts)

## Key concepts: three flows

Supporting Instant Checkout in ChatGPT requires implementing three flows.

### 1. Sharing a product feed

[Product feeds](https://developers.openai.com/commerce/product-feeds) define how merchants share structured product data with OpenAI so ChatGPT can surface products in search and shopping.

- Provide a **secure, regularly refreshed feed** as `jsonl.gz` or `csv.gz` (UTF-8): identifiers, descriptions, pricing, inventory, media, fulfillment. See **[docs/PRODUCT_FEED.md](PRODUCT_FEED.md)** for onboarding path, delivery (SFTP/upload/hosted URL), required vs recommended fields, and best practices.
- **Required fields** ensure correct price and availability; **recommended attributes** (rich media, reviews, performance signals) improve ranking and trust.
- Integration: validate with a small sample, then deliver **full snapshot** (stable filename, overwrite); **cadence** at least daily.

### 2. Handling orders and checkout

The [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout) lets ChatGPT act as the customer’s AI agent and render checkout inside ChatGPT’s UI.

- ChatGPT collects **buyer, fulfillment, and payment** information from the user.
- ChatGPT calls **your** Agentic Commerce Protocol endpoints to create/update a checkout session and share that information securely.
- **You** validate, compute fulfillment options, calculate and charge sales tax, analyze payment/risk on your stack, and charge the payment method with your existing processor. **You** accept or decline the order and return that state to ChatGPT.
- ChatGPT shows the order confirmation (or decline) to the user.

The checkout session is **rendered in OpenAI’s UI**, but **checkout state and payment processing happen on your systems**. You decide whether to accept or decline, charge the payment method, and confirm the order—all on your own systems.

### 3. Handling payments

The [Delegated Payment Spec](https://developers.openai.com/commerce/specs/payment) lets OpenAI securely share payment details with you or your PSP. You (and your PSP) then process the transaction like any other order.

- OpenAI prepares a **one-time delegated payment request** with a **maximum chargeable amount and expiry** based on what the user selected in ChatGPT.
- That payload goes to **your trusted PSP**, which handles the transaction.
- The PSP returns a **payment token**; OpenAI passes it to you to complete the payment.
- [Stripe’s Shared Payment Token](https://docs.stripe.com/agentic-commerce) is the first Delegated Payment–compatible implementation; eligible cards can use network tokenization. PSPs or PCI DSS Level 1 merchants with their own vault can [build a direct integration with OpenAI](https://developers.openai.com/commerce/specs/payment).

**OpenAI is not the merchant of record.** Merchants bring their own PSP and handle payments as they do for any other channel. The Delegated Payment Spec restricts how shared payment credentials may be used so user transactions stay secure.

### End-to-end flow

See the [Key concepts](https://developers.openai.com/commerce/guides/key-concepts) page for the end-to-end data flow diagram of the Agentic Commerce Protocol.

---

## Instant Checkout in ChatGPT

The first product built on the protocol is **Instant Checkout** in ChatGPT:

- Users buy **directly from you** inside ChatGPT (web, iOS, Android).
- You receive orders on your side and keep existing order/payment systems.
- Payment methods: major cards, Apple Pay, Google Pay, Link by Stripe, etc.

To enable Instant Checkout for SnapDish:

1. **Apply** — [Apply for Instant Checkout](https://chatgpt.com/merchants) (approved partners; rolling onboarding, starting in the U.S.).
2. **Product feed** — Provide OpenAI with a product feed per [Product feeds](https://developers.openai.com/commerce/product-feeds) (overview, onboarding, [feed spec](https://developers.openai.com/commerce/product-feeds/spec), [best practices](https://developers.openai.com/commerce/product-feeds/best-practices)).
3. **Agentic Checkout API** — Implement the [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout):
   - **REST:** `POST /checkout_sessions`, `POST /checkout_sessions/{id}`, `POST .../complete`, `POST .../cancel`, `GET /checkout_sessions/{id}`.
   - **Responses:** Return rich checkout state on every response (line items, fulfillment options, totals, messages, links).
   - **Webhooks:** Notify OpenAI of order events (e.g. `order.created`, `order.updated`).
4. **Payments** — Use a PSP that supports the [Delegated Payment Spec](https://developers.openai.com/commerce/specs/payment). [Stripe’s Shared Payment Token](https://docs.stripe.com/agentic-commerce) is the first compatible option; more PSPs coming. PCI DSS Level 1 merchants with their own vault can [integrate directly with OpenAI](https://developers.openai.com/commerce/specs/payment).
5. **Certify** — Pass OpenAI conformance checks and get production access.

*Etsy and Shopify merchants are already eligible and do not need to apply.*

## Agentic Checkout Spec summary

Enable end-to-end checkout inside ChatGPT while keeping orders, payments, and compliance on your stack.

**How it works**

1. **Create session (REST)** — ChatGPT calls `POST /checkout_sessions` with items and optional buyer/fulfillment_address; you return 201 and a rich cart state (id, payment_provider, status, currency, line_items, fulfillment_options, totals, messages, links).
2. **Update session (REST)** — On item, address, or fulfillment changes, ChatGPT calls `POST /checkout_sessions/{checkout_session_id}`; you return the full updated cart state.
3. **Order events (webhooks)** — You send `order_created` / `order_updated` to OpenAI’s webhook so ChatGPT stays in sync (payload includes checkout_session_id, status, refunds); sign with HMAC in a header (e.g. `Merchant_Name-Signature`).
4. **Complete checkout (REST)** — ChatGPT calls `POST /checkout_sessions/{checkout_session_id}/complete` with buyer and payment_data (token, provider, optional billing_address); you create the order, charge via your PSP, and return status and optional Order (id, checkout_session_id, permalink_url).
5. **Optional** — Cancel: `POST /checkout_sessions/{id}/cancel` (405 if already completed/canceled). Get: `GET /checkout_sessions/{id}` (404 if not found).
6. **Payments on your rails** — You charge with your existing PSP; with Delegated Payment, accept the token and run your normal auth/capture flow.

**Common request headers** (all endpoints): `Authorization` (Bearer), `Accept-Language`, `User-Agent`, `Idempotency-Key`, `Request-Id`, `Content-Type`, `Signature`, `Timestamp`, `API-Version`. **Response headers:** echo `Idempotency-Key` and `Request-Id`.

**Response errors** — On 4xx/5xx return JSON: `type` (e.g. `invalid_request`), `code` (e.g. `request_not_idempotent`), `message`, optional `param` (JSONPath to offending field).

**Checkout session status:** `not_ready_for_payment` | `ready_for_payment` | `completed` | `canceled`. Full object definitions (Item, Address, Buyer, LineItem, Total, FulfillmentOption, Message, Link, PaymentData, Order, webhook Event/EventData/Refund) are in the [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout).

## Implementation checklist (SnapDish)

| Step | Description | Links |
|------|-------------|--------|
| 1 | Apply to Instant Checkout | [chatgpt.com/merchants](https://chatgpt.com/merchants) |
| 2 | Define product catalog and feed format | [Product feeds spec](https://developers.openai.com/commerce/product-feeds/spec) |
| 3 | Implement checkout REST endpoints (create, update, complete, cancel, get) | [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout) |
| 4 | Implement webhooks for order lifecycle events | Same spec |
| 5 | Integrate Delegated Payment (e.g. Stripe) | [Delegated Payment](https://developers.openai.com/commerce/specs/payment), [Stripe Agentic Commerce](https://docs.stripe.com/agentic-commerce) |
| 6 | Security: auth, signature verification, idempotency, validation | [Production readiness](https://developers.openai.com/commerce/guides/production) |
| 7 | Certify with OpenAI and go to production | Via OpenAI partner process |

## Where it lives in this repo

- **docs/COMMERCE.md** — This file (overview and checklist).
- **docs/PRODUCT_FEED.md** — Product feed onboarding, delivery, condensed field reference, best practices; link to [Product Feed Spec](https://developers.openai.com/commerce/product-feeds/spec).
- **backend/snapdish/commerce_schemas.py** — Pydantic models for checkout session request/response (align with [checkout spec](https://developers.openai.com/commerce/specs/checkout)).
- **Backend API** — Add a commerce router when implementing; mount in `main.py` and use `commerce_schemas`. Product feed is generated separately (script or job) as `jsonl.gz` / `csv.gz`.

Once the Checkout API and product feed are implemented, Chef Marco (and ChatGPT) can recommend SnapDish products and complete purchases via Instant Checkout.
