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
