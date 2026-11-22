"""Session-based shopping cart."""
from decimal import Decimal

from store.models import Product

CART_SESSION_KEY = 'cart'


class Cart:
    """
    A session-backed cart.
    Stored as: { str(product_id): {'quantity': int, 'price': str} }
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = {}
            self.session[CART_SESSION_KEY] = cart
        self.cart = cart

    # ------------------------------------------------------------------ #
    # Mutation helpers
    # ------------------------------------------------------------------ #

    def add(self, product: Product, quantity: int = 1, override_qty: bool = False):
        """Add *quantity* of *product*, or set it when override_qty is True."""
        key = str(product.pk)
        if key not in self.cart:
            self.cart[key] = {'quantity': 0, 'price': str(product.price)}
        if override_qty:
            self.cart[key]['quantity'] = quantity
        else:
            self.cart[key]['quantity'] += quantity
        # Always refresh price snapshot
        self.cart[key]['price'] = str(product.price)
        self._save()

    def remove(self, product_id: int):
        key = str(product_id)
        if key in self.cart:
            del self.cart[key]
            self._save()

    def clear(self):
        del self.session[CART_SESSION_KEY]
        self.session.modified = True

    # ------------------------------------------------------------------ #
    # Read helpers
    # ------------------------------------------------------------------ #

    def __iter__(self):
        """
        Yield cart-item dicts enriched with the live Product object,
        silently skipping products that have since been deleted.
        """
        product_ids = [int(k) for k in self.cart]
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
        for key, entry in list(self.cart.items()):
            pid = int(key)
            product = products.get(pid)
            if product is None:
                # Product was deleted – remove stale entry
                del self.cart[key]
                self._save()
                continue
            yield {
                'product': product,
                'quantity': entry['quantity'],
                'price': Decimal(entry['price']),
                'line_total': Decimal(entry['price']) * entry['quantity'],
            }

    def __len__(self) -> int:
        return sum(e['quantity'] for e in self.cart.values())

    def get_total_price(self) -> Decimal:
        return sum(
            Decimal(e['price']) * e['quantity'] for e in self.cart.values()
        )

    def is_empty(self) -> bool:
        return len(self.cart) == 0

    # ------------------------------------------------------------------ #
    # Private
    # ------------------------------------------------------------------ #

    def _save(self):
        self.session.modified = True
