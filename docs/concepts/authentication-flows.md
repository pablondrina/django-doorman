# Authentication Flows

Doorman provides three authentication flows: Magic Code (OTP), Magic Link (email), and Device Trust (skip-OTP). All flows ultimately create a Django session via the BridgeToken exchange mechanism.

---

## Magic Code Flow (OTP)

The primary flow for phone-first authentication. A 6-digit code is sent via WhatsApp/SMS/email and verified before creating a session.

### Steps

1. Customer enters phone number on the code request form.
2. `VerificationService.request_code()` normalizes the phone, checks rate limits (G9, G10, G11), invalidates previous codes, generates a new code, stores the HMAC digest, and sends the raw code via the configured sender.
3. Customer receives the code and enters it on the verify form.
4. `VerificationService.verify_for_login()` finds the latest valid code, compares the input against the stored HMAC digest using timing-safe comparison. On match, resolves (or creates) the customer via `CustomerResolver`.
5. A BridgeToken is created internally and immediately exchanged to create a Django session via `AuthBridgeService.exchange()`.
6. Customer is redirected to the target URL.

### Diagram

```
Customer          Browser              Doorman                   Sender
   |                 |                    |                        |
   |  enter phone    |                    |                        |
   |---------------->|  POST /code/request|                        |
   |                 |------------------->|                        |
   |                 |                    |--G9: rate limit------->|
   |                 |                    |--G11: cooldown-------->|
   |                 |                    |--G10: IP rate limit--->|
   |                 |                    |                        |
   |                 |                    |  generate code         |
   |                 |                    |  store HMAC digest     |
   |                 |                    |  send raw code-------->|
   |                 |                    |                        |---> WhatsApp/SMS/Email
   |                 |  redirect to       |                        |
   |                 |  /code/verify      |                        |
   |                 |<-------------------|                        |
   |                 |                    |                        |
   |  receive code   |                    |                        |
   |<----------------|--------------------------------------------+
   |                 |                    |                        |
   |  enter code     |                    |                        |
   |---------------->|  POST /code/verify |                        |
   |                 |------------------->|                        |
   |                 |                    |  HMAC compare          |
   |                 |                    |  (timing-safe)         |
   |                 |                    |                        |
   |                 |                    |  resolve customer      |
   |                 |                    |  (CustomerResolver)    |
   |                 |                    |                        |
   |                 |                    |  create BridgeToken    |
   |                 |                    |  exchange -> session   |
   |                 |                    |  django.auth.login()   |
   |                 |                    |                        |
   |                 |  redirect to       |                        |
   |                 |  target URL        |                        |
   |                 |<-------------------|                        |
   |  authenticated  |                    |                        |
   |<----------------|                    |                        |
```

---

## Magic Link Flow (Email)

One-click login via email. The customer receives a link containing a BridgeToken and clicks it to authenticate. No code entry required.

### Steps

1. Customer enters email on the magic link form.
2. `MagicLinkService.send_magic_link()` looks up the customer by email via `CustomerResolver`. If found, creates a BridgeToken with a longer TTL (default 15 min) and sends the exchange URL via email.
3. Customer clicks the link in their email.
4. `BridgeTokenExchangeView` receives the GET request with the token parameter, calls `AuthBridgeService.exchange()` which validates the token (G7), resolves the customer, creates/finds the Django User via IdentityLink, logs in, and redirects.

### Diagram

```
Customer          Email Client         Browser              Doorman
   |                 |                    |                    |
   |  enter email    |                    |                    |
   |------------------------------------------>               |
   |                 |                    |  POST /magic-link/ |
   |                 |                    |------------------->|
   |                 |                    |                    |
   |                 |                    |  resolve customer  |
   |                 |                    |  (by email)        |
   |                 |                    |                    |
   |                 |                    |  create BridgeToken|
   |                 |                    |  (TTL: 15 min)     |
   |                 |                    |                    |
   |                 |                    |  send email with   |
   |                 |                    |  exchange URL      |
   |                 |                    |------------------->|
   |                 |                    |  {"success": true} |
   |                 |  email arrives     |                    |
   |                 |<-------------------|                    |
   |                 |                    |                    |
   |  click link     |                    |                    |
   |---------------->|                    |                    |
   |                 |  GET /bridge/?t=TOKEN                   |
   |                 |------------------->|------------------->|
   |                 |                    |                    |
   |                 |                    |  G7: validate token|
   |                 |                    |  resolve customer  |
   |                 |                    |  get/create User   |
   |                 |                    |  mark token used   |
   |                 |                    |  django.auth.login |
   |                 |                    |                    |
   |                 |  redirect to       |                    |
   |                 |  target URL        |                    |
   |  authenticated  |<-------------------|                    |
   |<----------------|                    |                    |
```

---

## Device Trust Flow (Skip-OTP)

After a successful OTP verification, the customer can opt to trust their device. On subsequent visits from the same device, OTP verification is skipped.

### Steps

1. Customer completes OTP verification (Magic Code flow above).
2. Application calls `DeviceTrustService.trust_device()` on the response.
3. A `TrustedDevice` record is created with an HMAC digest of a random token. The raw token is set as an HttpOnly, Secure, SameSite=Lax cookie.
4. On the next login from this device, the application calls `DeviceTrustService.check_device_trust()` which reads the cookie, computes the HMAC, looks up the record, and confirms the customer matches.
5. If the device is trusted, the full OTP flow is bypassed.

### Diagram

```
                     TRUST PHASE (after successful OTP)

Customer          Browser              Doorman                  DB
   |                 |                    |                       |
   |  OTP verified   |                    |                       |
   |<----------------|<-------------------|                       |
   |                 |                    |                       |
   |                 |  trust_device()    |                       |
   |                 |------------------->|                       |
   |                 |                    |  generate raw token   |
   |                 |                    |  HMAC(raw_token)      |
   |                 |                    |  store digest--------->|
   |                 |                    |                       |
   |                 |  Set-Cookie:       |                       |
   |                 |  doorman_dt=<raw>  |                       |
   |                 |  HttpOnly; Secure  |                       |
   |                 |<-------------------|                       |
   |                 |                    |                       |


                     CHECK PHASE (next login)

Customer          Browser              Doorman                  DB
   |                 |                    |                       |
   |  enter phone    |                    |                       |
   |---------------->|  POST /code/request|                       |
   |                 |------------------->|                       |
   |                 |  Cookie: doorman_dt|                       |
   |                 |                    |                       |
   |                 |                    |  check_device_trust() |
   |                 |                    |  read cookie          |
   |                 |                    |  HMAC(cookie_value)   |
   |                 |                    |  lookup by hash------>|
   |                 |                    |  verify customer match|
   |                 |                    |                       |
   |                 |                    |  TRUSTED: skip OTP    |
   |                 |                    |  create session       |
   |                 |                    |  directly             |
   |                 |  redirect to       |                       |
   |                 |  target URL        |                       |
   |  authenticated  |<-------------------|                       |
   |<----------------|                    |                       |
```

### Revocation

- **Single device**: `DeviceTrustService.revoke_device(request, response)` -- revokes the device from the current cookie and clears it.
- **All devices for a customer**: `DeviceTrustService.revoke_all(customer_id)` -- bulk deactivation.
- **Expiry cleanup**: `DeviceTrustService.cleanup(days=7)` -- deletes expired records.

---

## Security Considerations

### Timing-Safe Comparison

All secret comparisons use timing-safe functions to prevent timing side-channel attacks:
- OTP verification: `hmac.compare_digest` on HMAC digests
- Device trust verification: HMAC digest lookup (hash computed before DB query)
- API key verification: `secrets.compare_digest` on the provided key

### HMAC Storage

Secrets are never stored in plaintext:
- **MagicCode**: `code_hash` is `HMAC-SHA256(SECRET_KEY, raw_code)`. The raw 6-digit code is sent to the customer and discarded from server memory.
- **TrustedDevice**: `token_hash` is `HMAC-SHA256(SECRET_KEY, raw_cookie_token)`. The raw token lives only in the HttpOnly cookie.
- **BridgeToken**: Stored as plaintext because it is the lookup key. Security comes from short TTL and single-use semantics.

### Rate Limiting

Three layers protect against brute-force and abuse:
- **G9 -- Target rate limit**: Max N code requests per phone/email in a sliding window (default: 5 in 15 min).
- **G10 -- IP rate limit**: Max N code requests per IP in a sliding window (default: 20 in 60 min).
- **G11 -- Cooldown**: Minimum interval between sends to the same target (default: 60s).
- **MagicCode.max_attempts**: Each code allows limited verification attempts (default: 5). Exceeding fails the code permanently.

### Open Redirect Prevention

All redirect URLs are validated via `safe_redirect_url()`:
- Uses Django's `url_has_allowed_host_and_scheme`.
- Only allows relative paths and hosts in `ALLOWED_REDIRECT_HOSTS`.
- Rejects external URLs, protocol-relative URLs (`//evil.com`), and backslash URLs (`\evil.com`).
- Fallback is always `LOGIN_REDIRECT_URL` (default: `/`).
- The `next` parameter is validated before being stored in the session and again before redirecting.
