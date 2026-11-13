# Floristería Yada — Python API

Backend for the **Floristería Yada** React SPA (`../client`). Built with **FastAPI**, **SQLAlchemy 2**, and **MySQL**. JSON uses **camelCase** so it matches the SPA (`fullName`, `expiresAt`, `imageUrl`, `inStock`).

## Requirements

- Python 3.12 or later
- MySQL 8
- (Optional) Node.js to run the SPA in `../client`

## Quick start

### 1. Create the database

```sql
CREATE DATABASE yada_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'yada'@'localhost' IDENTIFIED BY 'yada';
GRANT ALL PRIVILEGES ON yada_shop.* TO 'yada'@'localhost';
FLUSH PRIVILEGES;
```

Tables are created automatically on first startup, including a `companies` table. Existing rows are backfilled with the default company. Extra order columns (`subtotal`, `delivery_option`, `delivery_fee`) are added if missing. If that company has no users, an **Admin** account is seeded from `.env`. If it has no products, a small catalog is seeded.

### 2. Configure environment

From this folder (`server/`):

```powershell
Copy-Item .env.example .env
```

Edit `.env` to match your MySQL instance, set a real `JWT_SECRET`, and (for production) SMTP credentials so order emails go to `info@yadacr.com`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MYSQL_HOST` | `localhost` | Database host |
| `MYSQL_PORT` | `3306` | Database port |
| `MYSQL_USER` | `yada` | Database user |
| `MYSQL_PASSWORD` | `yada` | Database password |
| `MYSQL_DATABASE` | `yada_shop` | Database name |
| `JWT_SECRET` | (change this) | Signing key for access tokens |
| `JWT_EXPIRE_MINUTES` | `480` | Token lifetime (8 hours) |
| `CORS_ORIGINS` | Vite origins | Comma-separated allowed frontends |
| `API_PREFIX` | `/api` | Route prefix |
| `ADMIN_EMAIL` | `admin@yadacr.com` | Seeded admin (empty DB only) |
| `ADMIN_PASSWORD` | `YadaAdmin123!` | Seeded admin password |
| `DEFAULT_COMPANY_SLUG` | `yada` | Public company identifier (`X-Company-Id`) |
| `DEFAULT_COMPANY_NAME` | `Floristería Yada` | Display name for the default company |
| `DEBUG` | `true` in example | SQL echo, FastAPI debug, log order emails if SMTP is unset |
| `SMTP_HOST` | (empty) | SMTP server; required in production to send order mail |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` / `SMTP_PASSWORD` | (empty) | SMTP login |
| `SMTP_FROM` | `Floristería Yada <info@yadacr.com>` | From header |
| `SMTP_USE_TLS` | `true` | STARTTLS |
| `ORDER_NOTIFY_EMAIL` | `info@yadacr.com` | Inbox for new order requests |
| `FRONTEND_URL` | `http://localhost:5173` | Origin used in password-reset links |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `60` | Reset-link lifetime |

If `SMTP_HOST` is empty and `DEBUG=true`, checkout still succeeds and the email body is written to the server log. In production (`DEBUG=false`), configure SMTP so shop staff receive the notification.

### 3. Install and run

Always start the process from **`server/`** (package imports are `app.*`).

```powershell
cd "D:\GitHub Projects\Shopping Cart\server"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5000
```

If a virtualenv already exists at `app\.venv`, activate that instead; still run uvicorn from `server/`.

API: [http://localhost:5000](http://localhost:5000)

| URL | Description |
|-----|-------------|
| [http://localhost:5000/](http://localhost:5000/) | Health check |
| [http://localhost:5000/docs](http://localhost:5000/docs) | Swagger UI |
| [http://localhost:5000/redoc](http://localhost:5000/redoc) | ReDoc |

## Connect the SPA

The Vite app proxies `/api` to port **5000**. In `../client`, copy `.env.example` to `.env`:

```env
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://localhost:5000
VITE_COMPANY_ID=yada
```

Then:

```powershell
cd ../client
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and use **Entrar** with the seeded admin or a registered account.

## HTTP API

Auth column: **No** = public, **JWT** = any logged-in user, **Admin** = role `Admin`.

Every `/api/*` route requires the header **`X-Company-Id`** with the company slug (for example `yada`). Data is isolated per company: users, products, customers, orders, order items/events, password-reset tokens, and contact messages all store `company_id`. Email uniqueness is per company. The health check `GET /` does not need the header.

To serve another shop, insert a row in `companies` and point a second SPA at that slug with `VITE_COMPANY_ID`.

### Health

| Method | Path | Auth |
|--------|------|------|
| GET | `/` | No |

```json
{ "status": "ok", "name": "Floristería Yada API" }
```

### Authentication

| Method | Path | Auth | Body |
|--------|------|------|------|
| POST | `/api/auth/login` | No | `{ "email", "password" }` |
| POST | `/api/auth/register` | No | `{ "email", "password", "fullName", "phone?" }` |
| POST | `/api/auth/forgot-password` | No | `{ "email" }` |
| POST | `/api/auth/reset-password` | No | `{ "token", "password" }` |
| GET | `/api/auth/me` | JWT | — |

Register requires a password of at least 8 characters. New accounts get role `Customer` and a matching CRM row in `customers`.

Forgot-password always returns the same message (it does not reveal whether the email exists). If the account exists, the API emails a one-hour link to `{FRONTEND_URL}/restablecer-contrasena?token=...`. The raw token is never stored; only a SHA-256 hash is kept in `password_reset_tokens`.

**Login / register response:**

```json
{
  "token": "eyJ...",
  "expiresAt": "2026-10-21T19:00:00Z",
  "user": {
    "id": "uuid",
    "email": "admin@yadacr.com",
    "fullName": "Administrador Yada",
    "roles": ["Admin"],
    "companyId": "uuid-of-company"
  }
}
```

Send the token as `Authorization: Bearer <token>`.

**Try it in Swagger**

1. `POST /api/auth/login` with `admin@yadacr.com` / `YadaAdmin123!` (first empty database).
2. Copy `token`.
3. Click **Authorize** and enter `Bearer <token>`.
4. Call `GET /api/auth/me`.

### Products

| Method | Path | Auth | Body |
|--------|------|------|------|
| GET | `/api/products` | No | — |
| GET | `/api/products/{id}` | No | — |
| POST | `/api/products` | Admin | `{ "name", "description?", "price", "imageUrl?", "category?", "inStock?" }` |
| PUT | `/api/products/{id}` | Admin | same as create |
| DELETE | `/api/products/{id}` | Admin | — |
| GET | `/api/product-categories` | No | — |
| POST | `/api/product-categories` | Admin | `{ "name" }` |
| PUT | `/api/product-categories/{id}` | Admin | `{ "name" }` |
| DELETE | `/api/product-categories/{id}` | Admin | — |

Product `category` must match a row in `product_categories` (or be omitted). Renaming a category updates products that used the old name; deleting one clears that field on those products. Missing category rows are seeded from existing product names (and the default catalog) when a company has none.

### Customers (CRM) and clients (registered accounts)

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/customers` | Admin |
| GET | `/api/customers/{id}` | Admin |
| POST | `/api/customers` | Admin |
| PUT | `/api/customers/{id}` | Admin |
| DELETE | `/api/customers/{id}` | Admin |
| GET | `/api/clients` | Admin |
| GET | `/api/clients/{id}` | Admin |

`customers` are CRM records (walk-in or admin-created). `clients` are user accounts with role `Customer`.

**Customer upsert:** `{ "fullName", "email", "phone?", "address?", "notes?" }`

### Contact messages

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/contact-messages` | No |
| GET | `/api/contact-messages` | Admin |
| GET | `/api/contact-messages/{id}` | Admin |
| PATCH | `/api/contact-messages/{id}` | Admin (`{ "read": true }`) |
| DELETE | `/api/contact-messages/{id}` | Admin |

The public form stores the message, then emails `ORDER_NOTIFY_EMAIL`. The row is kept even if mail fails.

**Create body:** `{ "name", "email", "phone", "message" }`

### Shop contact details

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/contact-info` | No (`X-Company-Id` required) |
| PUT | `/api/contact-info` | Admin |

One row per company (`company_contacts`). Missing rows are created with the default Floristería Yada details. Admins edit heading, description, address, phone, hours, email, and Instagram / Facebook / WhatsApp URLs. The SPA contact page and footer read this payload.

**Update body:** `{ "heading", "description?", "address?", "phone?", "hours?", "email?", "instagramUrl?", "facebookUrl?", "whatsappUrl?" }`

### Orders

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/orders` | No |
| POST | `/api/orders/admin` | Admin |
| GET | `/api/orders/mine` | JWT |
| GET | `/api/orders/mine/{id}` | JWT |
| GET | `/api/orders/mine/{id}/history` | JWT |
| GET | `/api/orders` | Admin |
| GET | `/api/orders/{id}` | Admin |
| GET | `/api/orders/{id}/history` | Admin |
| PUT | `/api/orders/{id}` | Admin |
| GET / POST / PUT / DELETE | `/api/discount-codes` | Admin |
| POST | `/api/discount-codes/preview` | No (optional JWT) |
| GET | `/api/loyalty/me` | JWT |
| GET | `/api/loyalty/accounts/{userId}` | Admin |
| GET | `/api/loyalty/members` | Admin |
| GET / POST / PUT / DELETE | `/api/loyalty/rewards` | Admin |

Checkout (`POST`) stores the order, then emails `ORDER_NOTIFY_EMAIL`. The order is saved even if mail fails. Home delivery requires `deliveryAddress`. If the shopper is logged in, the order is linked to their user id. `GET /api/orders/mine` returns orders for that user id **or** the same email as the account (so guest checkouts still appear after they register). Admins can place an order for someone else with `POST /api/orders/admin` (same body plus optional `userId`); the order is linked to that customer account, not the admin, and history records the administrator as the actor.

**Checkout body:**

```json
{
  "customerName": "Ana Flores",
  "customerEmail": "ana@yadacr.com",
  "customerPhone": "8888-1111",
  "deliveryAddress": "Hatillo 3",
  "deliveryOption": "up_to_5km",
  "notes": "Entregar mañana",
  "items": [{ "productId": 1, "quantity": 2 }]
}
```

Line prices come from the catalog, not the client. `total` = product subtotal − discount − loyalty discount + delivery fee.

**Loyalty** is for registered accounts only. A star is added when an order with a `userId` is marked `delivered` (`Entregado`) and removed if that status changes to anything else. Admins configure rewards (`name`, `description`, `ordersRequired`, `kind`: `percent` | `free_delivery` | `custom`). After N stars the customer can redeem on a later checkout (`loyaltyRewardId`). Promo codes and loyalty rewards cannot be combined.

**Delivery options** live in `delivery_fees` (per company). `GET /api/delivery-fees` is public. `PUT /api/delivery-fees` is Admin and replaces the full list: include `id` to update a row, omit `id` to add one, omit a row to delete it. Each option has `label`, `fee`, and `requiresAddress`. New options get a unique `code` from the label. Checkout looks up the fee for `deliveryOption` by that code. Defaults are seeded only when a company has zero rows (`pickup` $0, `up_to_2km` $5, `up_to_5km` $10, `over_5km` $20). At least one option is required.

**Order statuses** (admin `PUT`): `payment_pending` (default), `paid`, `preparing`, `ready_for_pickup`, `out_for_delivery`, `delivered`, `cancelled`.

Admin `PUT` may also change contact fields, `deliveryAddress`, `deliveryOption` (recalculates fee and total), `notes`, and `total`. When `status` actually changes, the API emails the customer (`customerEmail`) with the new status after the row is saved. The update still succeeds if mail fails.

Order history lives in `order_events`: `created` at checkout, `status_changed` on each admin status update, and `completed` when the status becomes `delivered`. Existing orders are backfilled with a creation event (and a reconstructed status/completion event when needed). Both customers and admins can read the timeline for orders they are allowed to see.

### Errors

Failed requests return a problem payload:

```json
{
  "title": "Invalid credentials",
  "detail": "Email or password is incorrect.",
  "status": 401,
  "errors": {}
}
```

## Project layout

```
server/
  .env.example
  requirements.txt
  app/
    main.py          # FastAPI app, CORS, table create, admin + catalog seed
    config.py        # Settings from environment
    database.py      # Engine, session, column backfill
    security.py      # bcrypt + JWT
    deps.py          # DB, current user, admin
    errors.py        # Problem JSON handlers
    mail.py          # Order notification email
    delivery.py      # Delivery option fees
    order_status.py  # Order status values
    order_history.py # Order timeline events
    seed.py          # Catalog seed
    models/          # users, products, customers, orders, order_items, order_events
    schemas/         # Pydantic request/response models
    routers/
      auth.py
      products.py
      customers.py
      clients.py
      orders.py
      contact.py
```

## Data model (MySQL)

On startup, SQLAlchemy creates (or extends):

- **users** — accounts (`id` UUID, email, hashed password, role `Admin` or `Customer`)
- **password_reset_tokens** — hashed, single-use reset links with expiry
- **products** — catalog (name, description, price, image, category, stock)
- **product_categories** — named catalog groups per company
- **customers** — CRM records (name, email, phone, address, notes)
- **orders** — checkout requests (contact, address, status, delivery option/fee, discount, subtotal, total)
- **discount_codes** — promo codes (percent, max discount, max redemptions, expiry, description)
- **discount_code_redemptions** — one use per customer email (and user) per code; overall uses cannot exceed `maxRedemptions`
- **loyalty_rewards** — punch-card rewards (orders required, kind, percent/max for discounts)
- **loyalty_redemptions** — registered-user redemptions of a loyalty reward on an order
- **order_items** — line snapshots (product name, quantity, unit price)
- **order_events** — history (created, status_changed, completed) with actor and timestamp
- **contact_messages** — contact form submissions (name, email, message, read_at)
