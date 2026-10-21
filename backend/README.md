# WanderLink API

FastAPI backend for the WanderLink travel site. It uses SQLAlchemy 2, PostgreSQL, Argon2 password hashes, and signed JWT access tokens.

The schema follows the supplied ERD: all entity IDs are auto-incrementing integers, schedules use `departure_time` and `arrival_time`, and bookings reference a target with uppercase `item_type` (`FLIGHT`, `HOTEL`, or `BUS`) and integer `item_id`.

The service now supports tenant isolation and RBAC: agencies own users, inventory, bookings, and subscriptions. Resolve a storefront through its host (for local development, use `agency.localhost`) and pass that host through any trusted reverse proxy. Full tenant rules, Stripe billing design, and storefront/dashboard route split are documented in [SAAS-ARCHITECTURE.md](./SAAS-ARCHITECTURE.md).

## Run locally

1. Create and activate a Python virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   py -m pip install -r requirements.txt
   ```

2. Create a PostgreSQL database named `wanderlink`. Copy `.env.example` to `.env`, update `DATABASE_URL`, and generate a private signing key:

   ```powershell
   py -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Put the generated value in `JWT_SECRET_KEY`. Keep `.env` private and do not commit it.

   To enable Stripe subscriptions, also configure the Stripe secret key, webhook signing secret, and the Stripe Price IDs for Basic and Pro in `.env`.

3. From the `backend` directory, create the initial tables:

   ```powershell
   py -m app.init_db
   ```

4. Create the initial platform administrator securely (password is entered with hidden input):

   ```powershell
   py -m app.create_platform_admin
   ```

5. Start the API:

   ```powershell
   py -m uvicorn app.main:app --reload
   ```

   Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

`init_db` is a convenient development bootstrap and does not update existing schemas. This ERD alignment changes primary-key types and the booking reference structure; an existing database needs a deliberate data migration before deploying the new models. Use versioned migrations for production schema changes.

Because `item_id` points to different tables according to `item_type`, it cannot have a conventional database foreign key. The booking endpoint checks the corresponding table and row under a lock before reserving inventory. Deleting referenced travel options should be restricted by application policy or handled with a booking-aware migration.

## Routes

- `POST /api/auth/register/` — register; passwords must be at least 10 characters.
- `POST /api/auth/login/` — exchange email and password for a bearer access token.
- `POST /api/auth/platform/login/` — authenticate a platform administrator created through a secure bootstrap process.
- `GET /api/public/agency/` — return the brand for the request host's agency.
- `GET /api/flights/search/?from=New%20York&to=London&date=2026-12-01` — flight search. Dates use the UTC calendar day.
- `GET /api/hotels/search/?location=Tokyo&check_in=2026-12-01&check_out=2026-12-04` — available hotel search.
- `GET /api/buses/search/?from=Boston&to=New%20York&date=2026-12-01` — bus search.
- `POST /api/bookings/create/` — reserve one flight, hotel, or bus option.
- `GET /api/user/bookings/` — list the authenticated user's bookings.
- `GET /api/agency/dashboard/`, `PATCH /api/agency/brand/`, and `GET /api/agency/bookings/` — agency-admin dashboard APIs.
- `POST /api/agency/inventory/flights/`, `/hotels/`, `/buses/` — add agency inventory.
- `POST /api/agency/billing/checkout/` with `{"plan":"BASIC"}` or `{"plan":"PRO"}` — create a Stripe subscription checkout session.
- `POST /api/agency/billing/portal/` — open Stripe Billing Portal for an existing subscription.
- `POST /api/platform/agencies/` and `GET /api/platform/agencies/` — platform-admin agency provisioning and listing.
- `GET /api/platform/subscriptions/` — platform-admin subscription overview.
- `POST /api/webhooks/stripe/` — Stripe-signed subscription lifecycle webhook.

The booking table also stores `quantity`, `passenger_details`, and hotel `check_in`/`check_out` dates for the booking workflow. Flight and bus bookings require one passenger entry per seat. Hotel bookings use `quantity` for rooms and require stay dates; their price is nightly rate × nights × rooms. Statuses are uppercase (`PENDING`, `CONFIRMED`, `CANCELLED`). Inventory is reserved while the transaction commits; payment and cancellation flows should confirm or release it in a future payment workflow.

Example flight booking payload:

```json
{
  "item_type": "FLIGHT",
  "item_id": 42,
  "quantity": 1,
  "passenger_details": [
    {
      "full_name": "Alex Traveler",
      "email": "alex@example.com",
      "phone": "+1 555 010 0100"
    }
  ]
}
```

## JWT from the frontend

Send the login response's `access_token` on each protected request in the standard Authorization header:

```js
fetch("http://127.0.0.1:8000/api/bookings/create/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify(booking),
});
```

Restrict `CORS_ORIGINS` to the actual frontend origins in deployment. Do not store long-lived tokens in publicly accessible storage.
