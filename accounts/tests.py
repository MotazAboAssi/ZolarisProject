"""
Accounts app tests.

Covers:
  - Registration (valid, invalid, duplicate email/username)
  - Signal auto-creates Profile on User creation
  - Login / logout
  - Profile view requires authentication
  - Profile editing (fields + image upload)
  - Admin registration of Profile
"""
import io
import tempfile
from PIL import Image as PILImage

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='testuser', password='Str0ngPass!', email='test@example.com', **kw):
    return User.objects.create_user(username=username, password=password, email=email, **kw)


def tiny_image():
    """Return a minimal valid JPEG as a SimpleUploadedFile."""
    buf = io.BytesIO()
    img = PILImage.new('RGB', (10, 10), color=(255, 0, 0))
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('test.jpg', buf.read(), content_type='image/jpeg')


# ---------------------------------------------------------------------------
# Profile model / signal tests
# ---------------------------------------------------------------------------

class ProfileSignalTest(TestCase):

    def test_profile_created_on_user_save(self):
        """Signal must create a Profile automatically."""
        user = make_user()
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_no_duplicate_profile(self):
        """Saving the user again must not create a second Profile."""
        user = make_user()
        user.first_name = 'Updated'
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_profile_str(self):
        user = make_user()
        self.assertIn(user.username, str(user.profile))

    def test_profile_full_name_fallback(self):
        """full_name property returns username when first/last name are absent."""
        user = make_user()
        self.assertEqual(user.profile.full_name, user.username)

    def test_profile_full_name_with_names(self):
        user = make_user(first_name='Alice', last_name='Smith')
        self.assertEqual(user.profile.full_name, 'Alice Smith')


# ---------------------------------------------------------------------------
# Registration view tests
# ---------------------------------------------------------------------------

class RegistrationViewTest(TestCase):

    URL = '/accounts/register/'

    def test_register_page_loads(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')

    def test_register_url_name(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)

    def test_valid_registration(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        response = self.client.post(self.URL, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_registration_creates_profile(self):
        data = {
            'username': 'signaluser',
            'email': 'signal@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        self.client.post(self.URL, data)
        user = User.objects.get(username='signaluser')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_registration_logs_user_in(self):
        data = {
            'username': 'autologin',
            'email': 'autologin@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        response = self.client.post(self.URL, data, follow=True)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_missing_username_invalid(self):
        data = {
            'username': '',
            'email': 'x@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        response = self.client.post(self.URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='x@example.com').exists())

    def test_password_mismatch_invalid(self):
        data = {
            'username': 'mismatch',
            'email': 'mm@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'Different!Pass1',
        }
        response = self.client.post(self.URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    def test_duplicate_email_rejected(self):
        make_user(email='dup@example.com')
        data = {
            'username': 'dupuser2',
            'email': 'dup@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        response = self.client.post(self.URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='dupuser2').exists())

    def test_duplicate_username_rejected(self):
        make_user(username='taken')
        data = {
            'username': 'taken',
            'email': 'other@example.com',
            'password1': 'C0mplexPass#99',
            'password2': 'C0mplexPass#99',
        }
        response = self.client.post(self.URL, data)
        self.assertEqual(response.status_code, 200)
        # Only one user with that username
        self.assertEqual(User.objects.filter(username='taken').count(), 1)

    def test_authenticated_user_redirected_from_register(self):
        make_user()
        self.client.login(username='testuser', password='Str0ngPass!')
        response = self.client.get(self.URL)
        self.assertRedirects(response, reverse('accounts:profile'))


# ---------------------------------------------------------------------------
# Login / logout tests
# ---------------------------------------------------------------------------

class LoginViewTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_valid_login(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'Str0ngPass!',
        }, follow=True)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_login(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout(self):
        self.client.login(username='testuser', password='Str0ngPass!')
        response = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


# ---------------------------------------------------------------------------
# Profile view tests
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileViewTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.url = reverse('accounts:profile')

    def test_profile_redirects_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_profile_loads_for_authenticated(self):
        self.client.login(username='testuser', password='Str0ngPass!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')

    def test_profile_edit_name(self):
        self.client.login(username='testuser', password='Str0ngPass!')
        response = self.client.post(self.url, {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'test@example.com',
            'bio': 'Hello world',
            'phone': '',
            'address': '',
            'city': '',
            'country': '',
            'postal_code': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Alice')
        self.assertEqual(self.user.last_name, 'Smith')

    def test_profile_edit_bio_and_address(self):
        self.client.login(username='testuser', password='Str0ngPass!')
        self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': 'test@example.com',
            'bio': 'I love Django!',
            'phone': '+1234567890',
            'address': '123 Main St',
            'city': 'Anytown',
            'country': 'Netherlands',
            'postal_code': '1234AB',
        })
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.bio, 'I love Django!')
        self.assertEqual(profile.city, 'Anytown')
        self.assertEqual(profile.country, 'Netherlands')

    def test_profile_edit_invalid_email(self):
        """Submitting a duplicate email must not save and re-render form."""
        other = make_user(username='other', email='other@example.com')
        self.client.login(username='testuser', password='Str0ngPass!')
        response = self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': 'other@example.com',  # already taken
            'bio': '',
            'phone': '',
            'address': '',
            'city': '',
            'country': '',
            'postal_code': '',
        })
        self.assertEqual(response.status_code, 200)
        # own email must not have changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')

    def test_profile_image_upload(self):
        self.client.login(username='testuser', password='Str0ngPass!')
        img = tiny_image()
        response = self.client.post(self.url, {
            'first_name': '',
            'last_name': '',
            'email': 'test@example.com',
            'bio': '',
            'phone': '',
            'address': '',
            'city': '',
            'country': '',
            'postal_code': '',
            'image': img,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        profile = Profile.objects.get(user=self.user)
        self.assertTrue(bool(profile.image))
