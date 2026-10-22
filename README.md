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

Tables are created automatically on first startup. Extra order columns (`subtotal`, `delivery_option`, `delivery_fee`) are added if missing. If `users` is empty, an **Admin** account is seeded from `.env`. If `products` is empty, a small catalog is seeded.

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
| `DEBUG` | `true` in example | SQL echo, FastAPI debug, log order emails if SMTP is unset |
| `SMTP_HOST` | (empty) | SMTP server; required in production to send order mail |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` / `SMTP_PASSWORD` | (empty) | SMTP login |
| `SMTP_FROM` | `Floristería Yada <info@yadacr.com>` | From header |
| `SMTP_USE_TLS` | `true` | STARTTLS |
| `ORDER_NOTIFY_EMAIL` | `info@yadacr.com` | Inbox for new order requests |

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
| GET | `/api/auth/me` | JWT | — |

Register requires a password of at least 8 characters. New accounts get role `Customer` and a matching CRM row in `customers`.

**Login / register response:**

```json
{
  "token": "eyJ...",
  "expiresAt": "2026-10-21T19:00:00Z",
  "user": {
    "id": "uuid",
    "email": "admin@yadacr.com",
    "fullName": "Administrador Yada",
    "roles": ["Admin"]
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

### Orders

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/orders` | No |
| GET | `/api/orders` | Admin |
| GET | `/api/orders/{id}` | Admin |
| PUT | `/api/orders/{id}` | Admin |

Checkout (`POST`) stores the order, then emails `ORDER_NOTIFY_EMAIL`. The order is saved even if mail fails. Home delivery requires `deliveryAddress`.

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

Line prices come from the catalog, not the client. `total` = product subtotal + delivery fee.

**Delivery options**

| `deliveryOption` | Fee |
|------------------|-----|
| `pickup` | $0 (store pickup) |
| `up_to_2km` | $5 |
| `up_to_5km` | $10 |
| `over_5km` | $20 |

**Order statuses** (admin `PUT`): `payment_pending` (default), `paid`, `preparing`, `ready_for_pickup`, `out_for_delivery`, `delivered`, `cancelled`.

Admin `PUT` may also change contact fields, `deliveryAddress`, `deliveryOption` (recalculates fee and total), `notes`, and `total`.

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
    seed.py          # Catalog seed
    models/          # users, products, customers, orders, order_items
    schemas/         # Pydantic request/response models
    routers/
      auth.py
      products.py
      customers.py
      clients.py
      orders.py
```

## Data model (MySQL)

On startup, SQLAlchemy creates (or extends):

- **users** — accounts (`id` UUID, email, hashed password, role `Admin` or `Customer`)
- **products** — catalog (name, description, price, image, category, stock)
- **customers** — CRM records (name, email, phone, address, notes)
- **orders** — checkout requests (contact, address, status, delivery option/fee, subtotal, total)
- **order_items** — line snapshots (product name, quantity, unit price)
