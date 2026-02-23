# Doorman Contracts

Phone-first passwordless authentication for Django.

---

## Public API

### AuthBridgeService

Creates bridge tokens for chat-to-web authentication and exchanges them for Django sessions.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `create_token` | `(customer, audience?, source?, ttl_minutes?, metadata?)` | `TokenResult` | Create a BridgeToken for a customer. Emits `bridge_token_created`. |
| `exchange` | `(token_str, request, required_audience?, preserve_session_keys?)` | `AuthResult` | Exchange token for Django session. Atomic. Emits `customer_authenticated`. |
| `get_customer_for_user` | `(user)` | `DoormanCustomerInfo \| None` | Lookup customer via IdentityLink for a Django User. |
| `get_user_for_customer` | `(customer)` | `User \| None` | Lookup Django User via IdentityLink for a customer. |
| `cleanup_expired_tokens` | `(days=7)` | `int` | Delete expired tokens older than N days. |

### VerificationService

Handles OTP code generation, sending, and verification.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `request_code` | `(target_value, purpose?, delivery_method?, ip_address?, sender?)` | `CodeRequestResult` | Generate and send a 6-digit OTP. Invalidates previous codes. Emits `magic_code_sent`. |
| `verify_for_login` | `(target_value, code_input, request?)` | `VerifyResult` | Verify OTP for login. Creates customer if `AUTO_CREATE_CUSTOMER=True`. Atomic. Emits `magic_code_verified`. |
| `cleanup_expired_codes` | `(days=7)` | `int` | Delete expired codes older than N days. |

### DeviceTrustService

Manages device trust cookies for skip-OTP repeat logins.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `check_device_trust` | `(request, customer_id)` | `bool` | Check if current device is trusted for this customer. |
| `trust_device` | `(response, customer_id, request)` | `TrustedDevice \| None` | Create trusted device record and set HttpOnly cookie. |
| `revoke_device` | `(request, response)` | `None` | Revoke current device trust and clear cookie. |
| `revoke_all` | `(customer_id)` | `int` | Revoke all trusted devices for a customer. |
| `cleanup` | `(days=7)` | `int` | Delete expired device trust records. |

### MagicLinkService

Email-based one-click passwordless login. Reuses BridgeToken infrastructure.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `send_magic_link` | `(email, sender?)` | `MagicLinkResult` | Find customer by email, create BridgeToken, send URL via email. |

---

## Invariants

These properties always hold and are never violated:

1. **OTP codes stored as HMAC-SHA256** -- The raw 6-digit code is never persisted. Only the HMAC-SHA256 digest (keyed with `OTP_HMAC_KEY` or `SECRET_KEY`) is stored in `MagicCode.code_hash`. Verification uses `hmac.compare_digest` for timing-safe comparison.

2. **Bridge tokens are single-use** -- After `mark_used()`, the token cannot be exchanged again. A 60-second reuse window (`BRIDGE_TOKEN_REUSE_WINDOW_SECONDS`) allows browser prefetch/prerender to not fail the real click.

3. **All redirects validated against ALLOWED_REDIRECT_HOSTS** -- `safe_redirect_url()` uses Django's `url_has_allowed_host_and_scheme` to reject open redirect attacks. Only relative paths and configured hosts pass. Fallback is always `LOGIN_REDIRECT_URL`.

4. **API key required for bridge token creation** -- When `BRIDGE_TOKEN_API_KEY` is set, `POST /doorman/bridge/create/` requires `Authorization: Bearer <key>` or `X-Api-Key: <key>`. Comparison uses `secrets.compare_digest`. Empty key disables auth (dev only).

5. **Rate limiting per target and per IP** -- G9 limits code requests per phone/email within a sliding window. G10 limits requests per IP address. Both are enforced before code creation.

6. **Code cooldown prevents rapid re-sends** -- G11 enforces a minimum interval (default 60s) between code sends to the same target. Prevents wasting messaging credits and user confusion.

---

## Token Contracts

### BridgeToken

| Property | Value |
|----------|-------|
| TTL | `BRIDGE_TOKEN_TTL_MINUTES` (default: 5 min) |
| Single-use | Yes. `used_at` set on exchange. |
| Reuse window | 60 seconds after first use (browser prefetch tolerance) |
| Scope | `audience` field: `web_checkout`, `web_account`, `web_support`, `web_general` |
| Format | `secrets.token_urlsafe(32)` -- 43 characters, URL-safe |
| Storage | Plaintext (it is the lookup key; short TTL + single-use provide security) |
| Source tracking | `source` field: `manychat`, `internal`, `api` |

### MagicCode

| Property | Value |
|----------|-------|
| TTL | `MAGIC_CODE_TTL_MINUTES` (default: 10 min) |
| Max attempts | `MAGIC_CODE_MAX_ATTEMPTS` (default: 5) |
| Storage | HMAC-SHA256 digest only. Raw code never stored. |
| Cooldown | `MAGIC_CODE_COOLDOWN_SECONDS` (default: 60s) between sends to same target |
| Format | 6-digit numeric string (`000000`-`999999`) |
| Invalidation | Previous pending/sent codes for the same target+purpose are expired on new request |
| Verification | `hmac.compare_digest` (timing-safe) of HMAC digests |

### TrustedDevice

| Property | Value |
|----------|-------|
| TTL | `DEVICE_TRUST_TTL_DAYS` (default: 30 days) |
| Cookie | HttpOnly, Secure (production), SameSite=Lax |
| Cookie name | `DEVICE_TRUST_COOKIE_NAME` (default: `doorman_dt`) |
| Storage | HMAC-SHA256 of cookie token. Raw token only in cookie, never in DB. |
| Revocation | Per-device (`revoke`) or per-customer (`revoke_all_for_customer`) |
| Token format | `secrets.token_urlsafe(32)` |

---

## Gates

| Gate | Name | Validates |
|------|------|-----------|
| G7 | BridgeTokenValidity | Token exists, not expired, not used (or within reuse window), audience matches if required |
| G8 | MagicCodeValidity | Code not expired, attempts < max, status is pending/sent, not already verified |
| G9 | RateLimit | Code request count for target within sliding window does not exceed max |
| G10 | IPRateLimit | Code request count for IP address within sliding window does not exceed max (default: 20/hour) |
| G11 | CodeCooldown | Minimum elapsed time since last code sent to same target (default: 60s) |

All gates raise `GateError` on failure. Each has a `check_*` variant that returns `bool` instead.

---

## Idempotency

| Operation | Safe to retry? | Notes |
|-----------|---------------|-------|
| `create_token` | Yes (creates new token each time) | Each call produces a distinct token. |
| `exchange` | Conditionally | Same token can be exchanged within 60s reuse window. After that, fails. |
| `request_code` | Conditionally | Cooldown (G11) blocks rapid retries. Previous codes are invalidated. |
| `verify_for_login` | No | Each retry consumes an attempt. After max attempts, code is failed. |
| `check_device_trust` | Yes | Read-only check (updates `last_used_at` on success). |
| `trust_device` | Yes (creates new device each time) | Each call creates a new TrustedDevice record. |
| `send_magic_link` | Yes (creates new token each time) | Each call creates a new BridgeToken and sends a new email. |
| `cleanup_*` | Yes | Deletes only already-expired records. |

---

## Integration Points

### CustomerResolver Protocol

Doorman is decoupled from customer storage via the `CustomerResolver` protocol:

```python
class CustomerResolver(Protocol):
    def get_by_phone(self, phone: str) -> DoormanCustomerInfo | None: ...
    def get_by_email(self, email: str) -> DoormanCustomerInfo | None: ...
    def get_by_uuid(self, uuid: UUID) -> DoormanCustomerInfo | None: ...
    def create_for_phone(self, phone: str) -> DoormanCustomerInfo: ...
```

Configure via `DOORMAN["CUSTOMER_RESOLVER_CLASS"]`. Default: `guestman.adapters.doorman.GuestmanCustomerResolver`.

### MessageSenderProtocol (Sender)

Doorman is decoupled from message delivery via the `MessageSenderProtocol`:

```python
class MessageSenderProtocol(Protocol):
    def send_code(self, target: str, code: str, method: str) -> bool: ...
```

Configure via `DOORMAN["MESSAGE_SENDER_CLASS"]`. Built-in senders: `ConsoleSender` (dev), `LogSender` (test), `WhatsAppCloudAPISender`, `SMSSender` (stub), `EmailSender`.

### Signals

| Signal | Emitted by | Kwargs |
|--------|-----------|--------|
| `bridge_token_created` | `AuthBridgeService.create_token` | `token`, `customer`, `audience`, `source` |
| `customer_authenticated` | `AuthBridgeService.exchange` | `customer`, `user`, `method`, `request` |
| `magic_code_sent` | `VerificationService.request_code` | `code`, `target_value`, `delivery_method` |
| `magic_code_verified` | `VerificationService.verify_for_login` | `code`, `customer`, `purpose` |
| `device_trusted` | (declared, emitted by consuming code) | `device`, `customer_id`, `request` |

---

## What Is NOT Doorman's Job

- **Customer management** -- Creating, updating, deactivating customers is Guestman's responsibility. Doorman only reads customer data via `CustomerResolver` and optionally triggers creation through `create_for_phone`.
- **Session management** -- Doorman creates Django sessions via `django.contrib.auth.login()` but does not manage session lifecycle, timeouts, or invalidation beyond login.
- **Order management** -- Cart preservation across login is supported via `PRESERVE_SESSION_KEYS`, but order/cart logic belongs to the commerce layer.
- **User profile management** -- `IdentityLink` maps Customer to User but Doorman does not manage user profiles, preferences, or permissions.
- **Message template management** -- WhatsApp templates, email templates content, and SMS copy are managed by the consuming application. Doorman only calls the configured sender.
