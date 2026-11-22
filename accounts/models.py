from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """Extended user profile linked one-to-one to Django built-in User."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    bio = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")

    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")

    image = models.ImageField(
        upload_to="profile_images/",
        blank=True,
        null=True,
        default=None,
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username
