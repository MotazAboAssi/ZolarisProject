from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'country', 'created')
    search_fields = ('user__username', 'user__email', 'city', 'country')
    raw_id_fields = ('user',)
