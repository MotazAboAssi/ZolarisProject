from decimal import Decimal
from importlib import import_module
from io import BytesIO
import tempfile

from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Product

seed_migration = import_module('store.migrations.0002_seed_default_categories')


def make_test_image(filename: str = 'test.png') -> SimpleUploadedFile:
    """Create a minimal valid PNG image in memory for upload tests."""
    buffer = BytesIO()
    image = Image.new('RGB', (40, 30), color=(30, 120, 200))
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/png')


class CategoryModelTests(TestCase):
    def test_slug_auto_populated_and_collision_safe(self):
        cat_a = Category.objects.create(name='Smart Phones')
        self.assertEqual(cat_a.slug, 'smart-phones')

        cat_b = Category.objects.create(name='Smart-Phones!')
        self.assertEqual(cat_b.slug, 'smart-phones-1')

    def test_default_categories_seeded_and_idempotent(self):
        expected_names = {
            'Electronics',
            'Clothing & Fashion',
            'Books & Stationery',
            'Home & Kitchen',
            'Sports & Outdoors',
            'Accessories',
        }
        existing_names = set(Category.objects.values_list('name', flat=True))
        self.assertTrue(expected_names.issubset(existing_names))

        # Every seeded category must have a non-empty slug
        for cat in Category.objects.filter(name__in=expected_names):
            self.assertTrue(bool(cat.slug))

        # Running the data migration again must be idempotent and preserve existing rows
        custom_cat = Category.objects.create(name='Custom Collectibles')
        count_before = Category.objects.count()
        seed_migration.seed_default_categories(apps, None)
        self.assertEqual(Category.objects.count(), count_before)
        self.assertTrue(Category.objects.filter(pk=custom_cat.pk).exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoreViewsTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_superuser(
            username='alice',
            email='alice@example.com',
            password='strong-password-123',
        )
        self.other_superuser = User.objects.create_superuser(
            username='admin2',
            email='admin2@example.com',
            password='strong-password-789',
        )
        self.buyer = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='strong-password-456',
        )
        self.electronics, _ = Category.objects.get_or_create(name='Electronics')
        self.books, _ = Category.objects.get_or_create(name='Books & Stationery')

        self.product = Product.objects.create(
            seller=self.seller,
            category=self.electronics,
            title='Mechanical Keyboard',
            description='Tactile switches with aluminum frame.',
            price=Decimal('129.99'),
            stock=5,
        )
        self.book = Product.objects.create(
            seller=self.other_superuser,
            category=self.books,
            title='Django Architecture Guide',
            description='Deep dive into modular Django apps.',
            price=Decimal('39.50'),
            stock=12,
        )

    def test_product_list_search_and_filters(self):
        url = reverse('store:product-list')

        # Search by keyword in description
        resp = self.client.get(url, {'q': 'aluminum'})
        self.assertEqual(resp.status_code, 200)
        self.assertQuerySetEqual(resp.context['products'], [self.product])

        # Filter by category slug
        resp = self.client.get(url, {'category': self.books.slug})
        self.assertQuerySetEqual(resp.context['products'], [self.book])

        # Filter by price range
        resp = self.client.get(url, {'min_price': '100', 'max_price': '200'})
        self.assertQuerySetEqual(resp.context['products'], [self.product])

        # Malformed price params should not raise 500
        resp = self.client.get(url, {'min_price': 'invalid', 'max_price': 'nan'})
        self.assertEqual(resp.status_code, 200)

    def test_product_list_pagination_splits_at_seven_and_preserves_query_params(self):
        for i in range(10):
            Product.objects.create(
                seller=self.seller,
                category=self.electronics,
                title=f'Gadget {i}',
                description='Bulk test gadget',
                price=Decimal('50.00'),
                stock=2,
            )
        url = reverse('store:product-list')
        params = {
            'q': 'Gadget',
            'category': self.electronics.slug,
            'min_price': '10',
            'max_price': '100',
        }

        page1 = self.client.get(url, params)
        self.assertEqual(page1.status_code, 200)
        self.assertTrue(page1.context['is_paginated'])
        self.assertEqual(len(page1.context['products']), 7)
        self.assertEqual(page1.context['paginator'].num_pages, 2)
        self.assertContains(page1, 'q=Gadget')
        self.assertContains(page1, f'category={self.electronics.slug}')
        self.assertContains(page1, 'min_price=10')
        self.assertContains(page1, 'max_price=100')
        self.assertContains(page1, 'page=2')

        page2 = self.client.get(url, {**params, 'page': 2})
        self.assertEqual(page2.status_code, 200)
        self.assertEqual(len(page2.context['products']), 3)
        self.assertIn('q=Gadget', page2.context['query_string'])
        self.assertIn(f'category={self.electronics.slug}', page2.context['query_string'])
        self.assertNotIn('page=', page2.context['query_string'])
        self.assertContains(page2, 'page=1')

    def test_storefront_nav_hides_seller_links_for_buyers_and_guests(self):
        url = reverse('store:product-list')

        # Anonymous guest
        anon_resp = self.client.get(url)
        self.assertNotContains(anon_resp, reverse('store:product-create'))
        self.assertNotContains(anon_resp, reverse('store:my-products'))

        # Regular authenticated buyer
        self.client.force_login(self.buyer)
        buyer_resp = self.client.get(url)
        self.assertNotContains(buyer_resp, reverse('store:product-create'))
        self.assertNotContains(buyer_resp, reverse('store:my-products'))

        # Superuser seller
        self.client.force_login(self.seller)
        seller_resp = self.client.get(url)
        self.assertContains(seller_resp, reverse('store:product-create'))
        self.assertContains(seller_resp, reverse('store:my-products'))

    def test_product_detail_owner_controls_and_cart_hook(self):
        url = reverse('store:product-detail', kwargs={'pk': self.product.pk})

        # Anonymous user sees product & Add to Cart, not Edit/Delete links
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Edit Product')
        self.assertNotContains(resp, 'Delete Product')
        self.assertContains(resp, 'Add to Cart')

        # Regular buyer does not see Edit/Delete links
        self.client.force_login(self.buyer)
        buyer_resp = self.client.get(url)
        self.assertNotContains(buyer_resp, 'Edit Product')
        self.assertNotContains(buyer_resp, 'Delete Product')

        # Non-owner superuser does not see Edit/Delete links
        self.client.force_login(self.other_superuser)
        other_super_resp = self.client.get(url)
        self.assertNotContains(other_super_resp, 'Edit Product')
        self.assertNotContains(other_super_resp, 'Delete Product')

        # Owning superuser sees Edit/Delete links
        self.client.force_login(self.seller)
        resp = self.client.get(url)
        self.assertContains(resp, 'Edit Product')
        self.assertContains(resp, 'Delete Product')

        # Cart endpoint accepts POST and redirects to cart detail
        cart_resp = self.client.post(
            reverse('orders:cart-add', kwargs={'product_id': self.product.pk}),
            {'quantity': 2},
        )
        self.assertRedirects(cart_resp, reverse('orders:cart-detail'))

    def test_product_create_restricted_to_superusers(self):
        url = reverse('store:product-create')

        # Anonymous redirected to accounts:login
        anon_resp = self.client.get(url)
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), anon_resp.url)

        # Regular buyer gets 403 Forbidden on GET and POST
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(url).status_code, 403)
        buyer_post = self.client.post(
            url,
            {
                'category': self.electronics.pk,
                'title': 'Buyer Blocked Item',
                'description': 'Should not be created.',
                'price': '19.99',
                'stock': 2,
            },
        )
        self.assertEqual(buyer_post.status_code, 403)
        self.assertFalse(Product.objects.filter(title='Buyer Blocked Item').exists())

        # Superuser can create with image upload
        self.client.force_login(self.seller)
        resp = self.client.post(
            url,
            {
                'category': self.electronics.pk,
                'title': 'USB-C Hub',
                'description': '7-in-1 aluminum USB-C docking station.',
                'price': '49.99',
                'stock': 8,
                'image': make_test_image('hub.png'),
            },
        )
        created = Product.objects.get(title='USB-C Hub')
        self.assertEqual(created.seller, self.seller)
        self.assertTrue(bool(created.image))
        self.assertRedirects(resp, created.get_absolute_url())

    def test_my_products_restricted_to_superusers(self):
        url = reverse('store:my-products')

        # Anonymous redirected to login
        anon_resp = self.client.get(url)
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), anon_resp.url)

        # Regular buyer gets 403 Forbidden
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(url).status_code, 403)

        # Superuser sees only their own products
        self.client.force_login(self.seller)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertQuerySetEqual(resp.context['products'], [self.product])

    def test_product_update_and_delete_enforce_superuser_and_ownership(self):
        update_url = reverse('store:product-update', kwargs={'pk': self.product.pk})
        delete_url = reverse('store:product-delete', kwargs={'pk': self.product.pk})

        # Regular buyer gets 403 Forbidden
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)

        # Even if a product were assigned to a regular buyer, buyer still gets 403
        legacy_product = Product.objects.create(
            seller=self.buyer,
            category=self.electronics,
            title='Legacy Buyer Item',
            description='Created before superuser restriction.',
            price=Decimal('25.00'),
            stock=1,
        )
        self.assertEqual(
            self.client.get(reverse('store:product-update', kwargs={'pk': legacy_product.pk})).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('store:product-delete', kwargs={'pk': legacy_product.pk})).status_code,
            403,
        )
        # Detail page also hides Edit/Delete for non-superuser
        legacy_detail = self.client.get(
            reverse('store:product-detail', kwargs={'pk': legacy_product.pk})
        )
        self.assertNotContains(legacy_detail, 'Edit Product')
        self.assertNotContains(legacy_detail, 'Delete Product')

        # Non-owner superuser gets 403 Forbidden
        self.client.force_login(self.other_superuser)
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

        # Owning superuser can update
        self.client.force_login(self.seller)
        resp = self.client.post(
            update_url,
            {
                'category': self.electronics.pk,
                'title': 'Mechanical Keyboard Pro',
                'description': 'Updated description.',
                'price': '149.99',
                'stock': 3,
            },
        )
        self.assertRedirects(resp, self.product.get_absolute_url())
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Mechanical Keyboard Pro')

        # Owning superuser can delete
        del_resp = self.client.post(delete_url)
        self.assertRedirects(del_resp, reverse('store:product-list'))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
