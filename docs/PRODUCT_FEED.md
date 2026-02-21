# Product feed — ChatGPT Instant Checkout

Onboarding product feeds in ChatGPT is for **approved partners** only. [Apply for access](https://chatgpt.com/merchants) first.

Use this doc with the [Product Feed Spec](https://developers.openai.com/commerce/product-feeds/spec) (full schema and validation rules) and [Best practices](https://developers.openai.com/commerce/product-feeds/best-practices).

## Implementation path

1. **Review the [Product Feed Spec](https://developers.openai.com/commerce/product-feeds/spec).** Confirm canonical field names, required attributes, data formats, and validation rules before generating your first export.
2. **Validate required fields.** Ensure every row has all required fields before full-feed delivery.
3. **Deliver your full snapshot feed.** Use SFTP, file upload, or hosted URL per your onboarding setup.

## Feed model and delivery

### Supported feed type

- **Full snapshot feed** — complete catalog export; treated as source of truth.
- **Cadence:** at least daily. Intraday price/availability changes are not supported; include them in the next snapshot.

### Delivery and file requirements

| Topic | Guidance |
|-------|----------|
| **Delivery** | Push to OpenAI via SFTP, file upload, or hosted URL. |
| **Formats** | `jsonl.gz` and `csv.gz` |
| **Encoding** | UTF-8 |
| **Filename** | Use a **stable** file name; overwrite the same file on each update (do not create a new name each run). |
| **Shards** | If using multiple shard files, keep the shard set stable and replace the same shard files on each update. |
| **Shard size** | Up to 500k items per shard; target shard files under ~500 MB. |

### Watch for ingestion failures

- Missing required fields  
- Outdated or non-spec field names  
- Malformed field values  

### Removals

- To remove a product: set `is_eligible_search=false` or omit it from the next full snapshot.

### Tracking

- Add feed attribution to `url` (e.g. `utm_medium=feed`) for feed-specific click tracking.
- Keep internal tracking parameters consistent across snapshots.

---

## Field reference (condensed)

Full definitions, validation rules, and examples are in the [Product Feed Spec](https://developers.openai.com/commerce/product-feeds/spec). Below: required vs recommended by category.

### OpenAI flags (required)

| Attribute | Description |
|-----------|-------------|
| `is_eligible_search` | `true`/`false` — surface in ChatGPT search. |
| `is_eligible_checkout` | `true`/`false` — purchasable in ChatGPT. Requires `is_eligible_search=true`. |

### Basic product data (required unless noted)

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `item_id` | Required | Unique per variant; max 100 chars; stable over time. |
| `title` | Required | Max 150 chars; avoid all-caps. |
| `description` | Required | Max 5,000 chars; plain text. |
| `url` | Required | Product page URL; HTTPS preferred; must resolve HTTP 200. |
| `gtin`, `mpn` | Optional | GTIN/UPC/ISBN; manufacturer part number. |

### Item information

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `brand` | Required | Max 70 chars. |
| `condition`, `product_category`, `material`, `dimensions`, `weight`, `age_group`, etc. | Optional | See spec for units and formats. |

### Media

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `image_url` | Required | Main image; JPEG/PNG; HTTPS preferred. |
| `additional_image_urls`, `video_url`, `model_3d_url` | Optional | Comma-separated for additional images. |

### Price & promotions

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `price` | Required | Number + ISO 4217 currency (e.g. `79.99 USD`). |
| `sale_price`, dates, `unit_pricing_measure`, `pricing_trend` | Optional | Sale price must be ≤ price. |

### Availability & inventory

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `availability` | Required | `in_stock`, `out_of_stock`, `pre_order`, `backorder`, `unknown`. |
| `availability_date` | Required if pre_order | ISO 8601. |
| `expiration_date`, `pickup_method`, `pickup_sla` | Optional | See spec. |

### Variants

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `group_id` | Required | Same for all variants in a group; max 70 chars. |
| `listing_has_variations` | Required | `true`/`false`. |
| `variant_dict`, `item_group_title`, `color`, `size`, `size_system`, etc. | Recommended / optional | JSON object for variant attributes. |

### Fulfillment

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `shipping` | Optional | Format: `country:region:service_class:price:min_handling_days:max_handling_days:min_transit_days:max_transit_days`. |
| `is_digital` | Optional | `true`/`false`. |

### Merchant info

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `seller_name` | Required (display) | Max 70 chars. |
| `seller_url` | Required | HTTPS preferred. |
| `seller_privacy_policy`, `seller_tos` | Required if `is_eligible_checkout=true` | HTTPS preferred. |
| `marketplace_seller` | Optional | For 3P/marketplace. |

### Returns

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `return_policy` | Required | URL; HTTPS preferred. |
| `accepts_returns`, `return_deadline_in_days`, `accepts_exchanges` | Optional | Use `return_deadline_in_days` for return window. |

### Geo

| Attribute | Requirement | Notes |
|-----------|-------------|--------|
| `target_countries`, `store_country` | Required | ISO 3166-1 alpha-2. |
| `geo_price`, `geo_availability` | Optional | Region-specific. |

### Optional (recommended for relevance/trust)

- **Performance:** `popularity_score`, `return_rate`  
- **Compliance:** `warning` / `warning_url`, `age_restriction`  
- **Reviews/Q&A:** `review_count`, `star_rating`, `store_review_count`, `store_star_rating`, `q_and_a`, `reviews`  
- **Related:** `related_product_id`, `relationship_type`  

---

## Best practices (summary)

- **Content:** Factual descriptions; plain or bullet text; valid, encoded URLs.  
- **Seller:** Consistent `seller_name` and policy links; durable `return_policy` URL.  
- **Eligibility:** Common rollout: `is_eligible_search=true`, `is_eligible_checkout=false` until checkout is ready.  
- **Shipping:** Format `shipping` exactly per spec; start with one nationally valid value.  
- **Variants:** One row per variant; unique `item_id`; same `group_id` per group; `listing_has_variations=true`; variant-specific `url`, `title`, `description`, `image_url`; use `variant_dict` and explicit columns.  
- **Delivery:** Full snapshots on a predictable cadence; stable filename/path; overwrite in place; validate with a small sample (e.g. ~100 items) then full snapshot, then automate.  

---

## Prohibited products

ChatGPT only allows products that are legal, safe, and appropriate for a general audience. Prohibited include (but are not limited to): adult content; age-restricted (e.g. alcohol, nicotine, gambling); harmful/dangerous materials; weapons; prescription-only medications; unlicensed financial products; legally restricted goods; illegal activities; deceptive practices. Merchants are responsible for compliance; OpenAI may remove products or ban sellers for violations.

---

## Where this lives in SnapDish

- **docs/PRODUCT_FEED.md** — This file (onboarding path, delivery, condensed field reference, best practices).  
- **TODO.md** — Product feed tasks (sample feed, full snapshot, delivery, validation).  
- **Feed generation** — Implement in a script or backend job that outputs `jsonl.gz` or `csv.gz` per spec; use the field list above and the [full spec](https://developers.openai.com/commerce/product-feeds/spec) for validation.
