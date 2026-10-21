# WanderLink multi-tenant SaaS architecture

## Tenant and data isolation

Every agency-owned row has a non-null `agency_id` foreign key. A user belongs to one agency, except platform administrators (`agency_id = NULL`). Customer emails are unique per agency, allowing the same person to have separate accounts on different storefronts. Tenant resolution uses the HTTP host: an exact custom domain or a subdomain under `PLATFORM_ROOT_DOMAIN`. For local development, `agency.localhost` resolves to the `agency` subdomain.

Do not trust an arbitrary `agency_id` query parameter or request body field for tenant selection. In production, route storefront traffic through a reverse proxy that preserves the original validated `Host` header when forwarding requests to FastAPI. If the API is hosted on a separate domain, have the trusted proxy pass the validated storefront host and configure the API to accept that proxy-only header; never treat a client-supplied tenant ID as authorization.

Public search and booking queries always filter by the resolved agency. Booking writes verify the inventory row belongs to that agency before locking or decrementing it. JWTs carry the user's agency and role; each request also checks those claims against the current database user, then tenant dependencies require membership in the host-resolved agency. Agency-admin routes additionally require `AGENCY_ADMIN`; platform administration requires `PLATFORM_ADMIN`. These are application-level row filters. PostgreSQL RLS can be added as defense-in-depth by setting a transaction-local tenant ID and adding tenant policies for every tenant table.

## Roles

- `PLATFORM_ADMIN`: no agency membership; creates and lists agencies and manages the SaaS platform.
- `AGENCY_ADMIN`: one agency; manages its storefront brand, inventory, booking ledger, and subscription.
- `CUSTOMER`: one agency; books and views only their own bookings in that agency.

Only the platform-admin agency provisioning endpoint creates agency-admin accounts. Public registration always creates a customer and cannot select its own role or tenant.

## Plans and Stripe

`AgencySubscription` stores the agency's plan, provider status, Stripe customer/subscription IDs, billing period, and cancellation flag. Basic permits 500 bookings per billing period and does not allow custom domains. Pro has no monthly booking cap and permits custom domains. Booking creation locks the agency and subscription rows before checking the quota, preventing simultaneous requests from overshooting the Basic limit.

Configure Stripe Price IDs for Basic and Pro in the environment. Agency administrators create a Stripe Checkout subscription session through `/api/agency/billing/checkout/`; the webhook `/api/webhooks/stripe/` verifies the Stripe signature, updates subscription state, and records event IDs for idempotency. Stripe credentials and webhook secrets stay server-side. Configure the production Stripe webhook for `checkout.session.completed` and `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`. A Pro custom domain must also be verified and DNS-routed before it is used; the API's plan check alone is not domain ownership verification.

## API surfaces

### Public customer storefront

- `GET /api/public/agency/` — brand configuration for the host-resolved agency.
- `GET /api/public/plans/` — public subscription feature list.
- `POST /api/auth/register/` and `/api/auth/login/` — customer accounts scoped to the current storefront host.
- `GET /api/flights/search/`, `/api/hotels/search/`, `/api/buses/search/` — search only current-agency inventory.
- `POST /api/bookings/create/` and `GET /api/user/bookings/` — customer booking flow, tenant- and user-scoped.

### Agency administration

- `GET /api/agency/dashboard/` — subscription and booking usage summary.
- `PATCH /api/agency/brand/` — update agency branding; custom domain requires Pro.
- `POST /api/agency/inventory/flights/`, `/hotels/`, `/buses/` — create tenant-owned inventory.
- `GET /api/agency/bookings/` — agency booking ledger.
- `POST /api/agency/billing/checkout/` — start or change a Basic/Pro subscription through Stripe Checkout.
- `POST /api/agency/billing/portal/` — manage an existing subscription through Stripe Billing Portal.

### Platform administration

- `POST /api/auth/platform/login/` — authenticate a seeded platform administrator.
- `POST /api/platform/agencies/` and `GET /api/platform/agencies/` — provision/list agencies. Provisioning also creates the agency admin and default Basic subscription.
- `GET /api/platform/subscriptions/` — platform-admin subscription and billing-period overview.

## Frontend split and white-labeling

Use a shared Next.js application with two separately guarded route groups:

- **Storefront**: `/`, `/flights`, `/hotels`, `/buses`, `/checkout`, `/account/bookings`. Middleware resolves the incoming hostname; server rendering fetches `/api/public/agency/` through the trusted API proxy. Apply the returned logo and colors through CSS custom properties:

  ```js
  document.documentElement.style.setProperty("--ocean", agency.primary_color);
  document.documentElement.style.setProperty("--teal", agency.secondary_color);
  ```

  Render `agency.logo_url` and keep contrast-safe text/action tokens separate from tenant brand colors.
- **Agency dashboard**: `/dashboard`, `/dashboard/inventory`, `/dashboard/bookings`, `/dashboard/analytics`, `/dashboard/branding`, `/dashboard/billing`. Every page calls authenticated agency endpoints; the API enforces the user's role and host tenant, so hiding UI controls is not the security boundary.
- **Platform console**: `/platform/agencies`, `/platform/subscriptions`, `/platform/usage`. These routes require a platform-admin login and call platform-only APIs.

In production, use wildcard DNS/TLS for `*.mysaas.com`; custom domains require domain verification, DNS instructions, and certificate provisioning before activation. Put migrations under Alembic; `Base.metadata.create_all()` is development-only and cannot safely convert an existing single-tenant database.
