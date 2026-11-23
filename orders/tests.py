"""
Automated tests for the orders app.
Covers: cart operations, stock validation, checkout, order history/detail,
        purchase-time price preservation, and access control.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from store.models import Category, Product

from .cart import Cart
from .models import Order, OrderItem


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def make_user(username='buyer', password='testpass123'):
    return User.objects.create_user(username=username, password=password)


def make_product(seller, title='Widget', price='9.99', stock=10):
    return Product.objects.create(
        seller=seller,
        title=title,
        description='A test widget.',
        price=Decimal(price),
        stock=stock,
    )


# ------------------------------------------------------------------ #
# Cart unit tests (session-based)
# ------------------------------------------------------------------ #

class CartAddTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller')
        self.product = make_product(self.seller)
        self.client = Client()

    def _add(self, product_id, quantity=1):
        return self.client.post(
            reverse('orders:cart-add', args=[product_id]),
            {'quantity': quantity},
        )

    def test_add_product_redirects_to_cart(self):
        resp = self._add(self.product.pk)
        self.assertRedirects(resp, reverse('orders:cart-detail'))

    def test_add_product_appears_in_cart(self):
        self._add(self.product.pk, quantity=2)
        resp = self.client.get(reverse('orders:cart-detail'))
        self.assertContains(resp, self.product.title)

    def test_add_increases_quantity(self):
        self._add(self.product.pk, quantity=2)
        self._add(self.product.pk, quantity=3)
        session = self.client.session
        cart_data = session['cart']
        self.assertEqual(cart_data[str(self.product.pk)]['quantity'], 5)

    def test_add_nonexistent_product_returns_404(self):
        resp = self._add(99999)
        self.assertEqual(resp.status_code, 404)

    def test_add_zero_quantity_rejected(self):
        resp = self._add(self.product.pk, quantity=0)
        self.assertRedirects(resp, reverse('store:product-detail', args=[self.product.pk]))
        session = self.client.session
        self.assertNotIn('cart', session)

    def test_add_negative_quantity_rejected(self):
        resp = self._add(self.product.pk, quantity=-1)
        self.assertRedirects(resp, reverse('store:product-detail', args=[self.product.pk]))

    def test_add_exceeds_stock_rejected(self):
        resp = self._add(self.product.pk, quantity=self.product.stock + 1)
        self.assertRedirects(resp, reverse('store:product-detail', args=[self.product.pk]))
        self.assertNotIn('cart', self.client.session)

    def test_add_out_of_stock_product_rejected(self):
        self.product.stock = 0
        self.product.save()
        resp = self._add(self.product.pk, quantity=1)
        self.assertRedirects(resp, reverse('store:product-detail', args=[self.product.pk]))


class CartUpdateRemoveTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller2')
        self.product = make_product(self.seller, stock=10)
        self.client = Client()
        # Pre-populate cart
        self.client.post(
            reverse('orders:cart-add', args=[self.product.pk]),
            {'quantity': 3},
        )

    def test_update_quantity(self):
        self.client.post(
            reverse('orders:cart-update', args=[self.product.pk]),
            {'quantity': 5},
        )
        session = self.client.session
        self.assertEqual(session['cart'][str(self.product.pk)]['quantity'], 5)

    def test_update_to_zero_removes_item(self):
        self.client.post(
            reverse('orders:cart-update', args=[self.product.pk]),
            {'quantity': 0},
        )
        session = self.client.session
        self.assertNotIn(str(self.product.pk), session.get('cart', {}))

    def test_remove_item(self):
        self.client.post(reverse('orders:cart-remove', args=[self.product.pk]))
        session = self.client.session
        self.assertNotIn(str(self.product.pk), session.get('cart', {}))

    def test_update_exceeds_stock_rejected(self):
        resp = self.client.post(
            reverse('orders:cart-update', args=[self.product.pk]),
            {'quantity': self.product.stock + 1},
        )
        # Quantity stays at 3
        session = self.client.session
        self.assertEqual(session['cart'][str(self.product.pk)]['quantity'], 3)


class CartTotalTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller3')
        self.p1 = make_product(self.seller, title='A', price='10.00', stock=5)
        self.p2 = make_product(self.seller, title='B', price='5.50', stock=5)
        self.client = Client()

    def test_total_calculation(self):
        self.client.post(reverse('orders:cart-add', args=[self.p1.pk]), {'quantity': 2})
        self.client.post(reverse('orders:cart-add', args=[self.p2.pk]), {'quantity': 3})
        # 2×10 + 3×5.50 = 36.50
        resp = self.client.get(reverse('orders:cart-detail'))
        self.assertContains(resp, '36.50')

    def test_empty_cart_shows_no_items(self):
        resp = self.client.get(reverse('orders:cart-detail'))
        self.assertNotContains(resp, '<tbody>')


# ------------------------------------------------------------------ #
# Checkout tests
# ------------------------------------------------------------------ #

class CheckoutTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller4')
        self.buyer = make_user('buyer4')
        self.product = make_product(self.seller, price='20.00', stock=5)
        self.client = Client()
        self.client.login(username='buyer4', password='testpass123')

    def _add(self, qty=2):
        self.client.post(
            reverse('orders:cart-add', args=[self.product.pk]),
            {'quantity': qty},
        )

    def test_checkout_empty_cart_redirects(self):
        resp = self.client.post(reverse('orders:checkout'))
        self.assertRedirects(resp, reverse('orders:cart-detail'))

    def test_checkout_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('orders:checkout'))
        self.assertNotEqual(resp.status_code, 200)

    def test_successful_checkout_creates_order(self):
        self._add(qty=2)
        resp = self.client.post(reverse('orders:checkout'))
        self.assertEqual(Order.objects.filter(user=self.buyer).count(), 1)

    def test_successful_checkout_clears_cart(self):
        self._add(qty=2)
        self.client.post(reverse('orders:checkout'))
        session = self.client.session
        self.assertEqual(session.get('cart', {}), {})

    def test_successful_checkout_decrements_stock(self):
        self._add(qty=2)
        self.client.post(reverse('orders:checkout'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_successful_checkout_correct_total(self):
        self._add(qty=2)
        self.client.post(reverse('orders:checkout'))
        order = Order.objects.get(user=self.buyer)
        self.assertEqual(order.total_price, Decimal('40.00'))

    def test_checkout_blocked_when_stock_insufficient(self):
        self._add(qty=2)
        # Drain stock between cart-add and checkout
        self.product.stock = 1
        self.product.save()
        self.client.post(reverse('orders:checkout'))
        # No order should be created
        self.assertEqual(Order.objects.filter(user=self.buyer).count(), 0)
        # Stock must NOT go negative
        self.product.refresh_from_db()
        self.assertGreaterEqual(self.product.stock, 0)

    def test_no_negative_stock(self):
        self._add(qty=2)
        self.product.stock = 0
        self.product.save()
        self.client.post(reverse('orders:checkout'))
        self.product.refresh_from_db()
        self.assertGreaterEqual(self.product.stock, 0)


# ------------------------------------------------------------------ #
# Purchase-time price preservation
# ------------------------------------------------------------------ #

class PurchaseTimePriceTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller5')
        self.buyer = make_user('buyer5')
        self.product = make_product(self.seller, price='15.00', stock=10)
        self.client = Client()
        self.client.login(username='buyer5', password='testpass123')

    def test_unit_price_snapshot_preserved(self):
        self.client.post(
            reverse('orders:cart-add', args=[self.product.pk]),
            {'quantity': 1},
        )
        self.client.post(reverse('orders:checkout'))

        # Change product price after order
        self.product.price = Decimal('99.99')
        self.product.save()

        order = Order.objects.get(user=self.buyer)
        item = order.items.first()
        self.assertEqual(item.unit_price, Decimal('15.00'))

    def test_product_title_snapshot_preserved(self):
        original_title = self.product.title
        self.client.post(
            reverse('orders:cart-add', args=[self.product.pk]),
            {'quantity': 1},
        )
        self.client.post(reverse('orders:checkout'))

        self.product.title = 'Completely Different Title'
        self.product.save()

        order = Order.objects.get(user=self.buyer)
        item = order.items.first()
        self.assertEqual(item.product_title, original_title)


# ------------------------------------------------------------------ #
# Order history & detail / access control
# ------------------------------------------------------------------ #

class OrderHistoryDetailTest(TestCase):
    def setUp(self):
        self.seller = make_user('seller6')
        self.buyer = make_user('buyer6')
        self.other = make_user('other6')
        self.product = make_product(self.seller, stock=20)
        self.client = Client()
        self.client.login(username='buyer6', password='testpass123')
        # Place one order (follow redirect to consume flash messages)
        self.client.post(
            reverse('orders:cart-add', args=[self.product.pk]),
            {'quantity': 1},
        )
        self.client.post(reverse('orders:checkout'), follow=True)
        self.order = Order.objects.get(user=self.buyer)

    def test_order_history_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('orders:order-history'))
        self.assertNotEqual(resp.status_code, 200)

    def test_order_history_shows_own_orders(self):
        resp = self.client.get(reverse('orders:order-history'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'#{self.order.pk}')

    def test_order_detail_accessible_by_owner(self):
        resp = self.client.get(reverse('orders:order-detail', args=[self.order.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_order_detail_forbidden_for_other_user(self):
        self.client.logout()
        self.client.login(username='other6', password='testpass123')
        resp = self.client.get(reverse('orders:order-detail', args=[self.order.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_order_history_status_filter(self):
        resp = self.client.get(
            reverse('orders:order-history') + '?status=pending'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'#{self.order.pk}')

    def test_order_history_filter_excludes_other_statuses(self):
        resp = self.client.get(
            reverse('orders:order-history') + '?status=delivered'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, f'#{self.order.pk}')

    def test_other_users_orders_not_in_history(self):
        # other user's order not in buyer's history
        resp = self.client.get(reverse('orders:order-history'))
        # Only buyer6's order should appear
        self.assertEqual(
            Order.objects.filter(user=self.buyer).count(),
            resp.context['page_obj'].paginator.count,
        )
