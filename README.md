# MiniShop — Django Mini E-Commerce Store

A modular, production-ready Django e-commerce scaffold featuring the complete **`store`** catalog & seller-management module, along with clean integration hooks for the **`accounts`** and **`orders`** modules.

## Project Structure

```text
ecommerce_project/
├── ecommerce_project/      # Project settings, root URLs, WSGI/ASGI
├── store/                  # Core Storefront & Seller CRUD module (Complete)
│   ├── admin.py            # Admin registration for Category & Product
│   ├── forms.py            # Bootstrap-styled ProductForm (with image upload)
│   ├── models.py           # Category & Product models
│   ├── tests.py            # Automated tests for models, views & permissions
│   ├── urls.py             # Namespaced store URLs (app_name = 'store')
│   ├── views.py            # CBVs: List, Detail, Create, Update, Delete
│   └── templates/store/    # Responsive Bootstrap 5 templates
├── accounts/               # Placeholder module for teammate (Auth & Profile hooks)
├── orders/                 # Placeholder module for teammate (Cart & Orders hooks)
├── templates/              # Global base.html & placeholder auth/cart templates
├── static/                 # Global static assets (css/main.css)
├── media/                  # Uploaded product images (gitignored)
├── manage.py
├── requirements.txt
└── .gitignore
```

## Quick Start

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```
4. **Create a superuser (to manage categories/products in Django Admin):**
   ```bash
   python manage.py createsuperuser
   ```
5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
6. Open `http://127.0.0.1:8000/` in your browser.

## `store` Module Features

- **Models (`store/models.py`)**:
  - `Category`: `name` (unique), `slug` (unique, auto-populated on save).
  - `Product`: `seller` (`User`), `category` (`Category`, `SET_NULL`), `title`, `description`, `price`, `image` (`upload_to='products/'`), `stock`, `created_at`, `updated_at`.
- **Storefront (`ProductListView`)**:
  - Keyword search across `title` and `description` via Django `Q` objects (`?q=...`).
  - Filtering by `category` slug (`?category=...`) and price range (`?min_price=...&max_price=...`).
  - Pagination (9 items/page) preserving all active search and filter parameters across page links.
- **Product Detail (`ProductDetailView`)**:
  - Two-column responsive layout, seller metadata, stock badge, and an **Add to Cart** form wired to `orders:cart-add`.
  - Owner-only **Edit** and **Delete** controls (`request.user == product.seller`).
- **Seller CRUD & Security**:
  - `ProductCreateView`: protected by `LoginRequiredMixin`; auto-assigns `seller = request.user`.
  - `ProductUpdateView` & `ProductDeleteView`: protected by `LoginRequiredMixin` and `UserPassesTestMixin` enforcing `self.get_object().seller == self.request.user`.

## Teammate Integration Hooks (`accounts` & `orders`)

The following settings and URL names are already wired across `base.html`, `store/templates/`, and `ecommerce_project/settings.py` so your teammate can drop in full implementations without modifying `store`:

| Setting / URL Name | Target App | Current Behavior |
| :--- | :--- | :--- |
| `LOGIN_URL = 'accounts:login'` | `accounts` | Uses Django's built-in `LoginView` with `templates/accounts/login.html` |
| `LOGIN_REDIRECT_URL = 'store:product-list'` | `accounts` | Redirects authenticated users to the storefront |
| `LOGOUT_REDIRECT_URL = 'store:product-list'` | `accounts` | Redirects after logout to the storefront |
| `accounts:register` | `accounts` | Placeholder view ready to be replaced by registration view |
| `accounts:profile` | `accounts` | Placeholder view ready to be replaced by user profile view |
| `orders:cart-detail` | `orders` | Placeholder view ready to be replaced by cart page |
| `orders:cart-add` (`<int:product_id>`) | `orders` | Accepts `POST` (`quantity`) from `product_detail.html`, shows info flash message, and redirects back |

## Verification & Testing

```bash
python manage.py check
python manage.py test
```

---

## Cart & Checkout — Orders App

### How the cart works

The shopping cart is **session-based** (no database table required). Each visitor gets a cart stored in Django's server-side session under the key `cart`. The cart dictionary maps `str(product_id)` to `{quantity, price}`, where `price` is a snapshot taken at add-time.

Key behaviours:
- **Add** (`POST /orders/cart/add/<id>/`) — adds the requested quantity; validates that quantity ≥ 1 and that the combined cart quantity does not exceed current stock.
- **Update** (`POST /orders/cart/update/<id>/`) — overwrites the item's quantity; quantity 0 or below removes the item.
- **Remove** (`POST /orders/cart/remove/<id>/`) — deletes the item from the cart.
- Deleted products are silently removed from the cart on the next page load.

### How checkout works

1. `GET /orders/checkout/` renders an order summary with the current cart.
2. `POST /orders/checkout/` runs inside a **database transaction**:
   - Re-validates every item's stock with `SELECT FOR UPDATE` to prevent race conditions.
   - Creates an `Order` and one `OrderItem` per cart line.
   - Each `OrderItem` stores a **snapshot** of the product's title and unit price at the time of purchase so historical orders remain accurate even after price changes.
   - Decrements `Product.stock` for each item.
   - Clears the session cart.
   - Redirects to the new order's detail page.

Empty-cart checkout is blocked at both GET and POST.

### Order history & detail

- `GET /orders/orders/` — paginated list of the authenticated user's own orders, with optional `?status=` filter.
- `GET /orders/orders/<pk>/` — detail view; returns HTTP 404 for any order not owned by the requesting user.

### Files created / modified

| File | Action |
|------|--------|
| `orders/models.py` | Created — `Order` + `OrderItem` models |
| `orders/cart.py` | Created — session `Cart` class |
| `orders/views.py` | Replaced — full cart, checkout, history & detail views |
| `orders/urls.py` | Replaced — all orders URL patterns |
| `orders/admin.py` | Replaced — admin registration with inline |
| `orders/migrations/0001_initial.py` | Created — DB migration |
| `orders/templates/orders/cart.html` | Created |
| `orders/templates/orders/checkout.html` | Created |
| `orders/templates/orders/order_history.html` | Created |
| `orders/templates/orders/order_detail.html` | Created |
| `orders/tests.py` | Created — 25 automated tests |
| `templates/base.html` | Updated — added "My Orders" nav link & footer link |
