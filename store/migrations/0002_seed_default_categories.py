from django.db import migrations
from django.utils.text import slugify

DEFAULT_CATEGORIES = [
    'Electronics',
    'Clothing & Fashion',
    'Books & Stationery',
    'Home & Kitchen',
    'Sports & Outdoors',
    'Accessories',
]


def seed_default_categories(apps, schema_editor):
    """Idempotently seed default storefront categories without altering existing ones."""
    Category = apps.get_model('store', 'Category')

    for name in DEFAULT_CATEGORIES:
        if Category.objects.filter(name=name).exists():
            continue

        base_slug = slugify(name) or 'category'
        candidate = base_slug
        counter = 1
        while Category.objects.filter(slug=candidate).exists():
            candidate = f'{base_slug}-{counter}'
            counter += 1

        Category.objects.get_or_create(
            name=name,
            defaults={'slug': candidate},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_categories, migrations.RunPython.noop),
    ]
