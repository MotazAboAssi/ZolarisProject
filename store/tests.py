from decimal import Decimal
from io import BytesIO
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Product


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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoreViewsTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='alice',
            password='strong-password-123',
        )
        self.other_user = User.objects.create_user(
            username='bob',
            password='strong-password-456',
        )
        self.electronics = Category.objects.create(name='Electronics')
        self.books = Category.objects.create(name='Books')

        self.product = Product.objects.create(
            seller=self.seller,
            category=self.electronics,
            title='Mechanical Keyboard',
            description='Tactile switches with aluminum frame.',
            price=Decimal('129.99'),
            stock=5,
        )
        self.book = Product.objects.create(
            seller=self.other_user,
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
        resp = self.client.get(url, {'category': 'books'})
        self.assertQuerySetEqual(resp.context['products'], [self.book])

        # Filter by price range
        resp = self.client.get(url, {'min_price': '100', 'max_price': '200'})
        self.assertQuerySetEqual(resp.context['products'], [self.product])

        # Malformed price params should not raise 500
        resp = self.client.get(url, {'min_price': 'invalid', 'max_price': 'nan'})
        self.assertEqual(resp.status_code, 200)

    def test_product_list_pagination_preserves_query_params(self):
        for i in range(12):
            Product.objects.create(
                seller=self.seller,
                category=self.electronics,
                title=f'Gadget {i}',
                description='Bulk test gadget',
                price=Decimal('50.00'),
                stock=2,
            )
        url = reverse('store:product-list')
        resp = self.client.get(url, {'q': 'Gadget', 'category': 'electronics', 'page': 2})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_paginated'])
        self.assertIn('q=Gadget', resp.context['query_string'])
        self.assertIn('category=electronics', resp.context['query_string'])
        self.assertNotIn('page=', resp.context['query_string'])

    def test_product_detail_owner_controls_and_cart_hook(self):
        url = reverse('store:product-detail', kwargs={'pk': self.product.pk})

        # Anonymous user sees product but not Edit/Delete links
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Edit Product')
        self.assertContains(resp, 'Add to Cart')

        # Owner sees Edit/Delete links
        self.client.force_login(self.seller)
        resp = self.client.get(url)
        self.assertContains(resp, 'Edit Product')
        self.assertContains(resp, 'Delete Product')

        # Placeholder cart hook accepts POST and redirects cleanly
        cart_resp = self.client.post(
            reverse('orders:cart-add', kwargs={'product_id': self.product.pk}),
            {'quantity': 2},
        )
        self.assertRedirects(cart_resp, url)

    def test_product_create_requires_login_and_assigns_seller(self):
        url = reverse('store:product-create')

        # Anonymous redirected to accounts:login
        anon_resp = self.client.get(url)
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn(reverse('accounts:login'), anon_resp.url)

        # Logged-in user can create with image upload
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

    def test_product_update_and_delete_enforce_ownership(self):
        update_url = reverse('store:product-update', kwargs={'pk': self.product.pk})
        delete_url = reverse('store:product-delete', kwargs={'pk': self.product.pk})

        # Non-owner gets 403 Forbidden
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

        # Owner can update
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

        # Owner can delete
        del_resp = self.client.post(delete_url)
        self.assertRedirects(del_resp, reverse('store:product-list'))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
