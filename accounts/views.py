from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def register_placeholder(request):
    """Placeholder registration hook for the teammate's accounts module."""
    return render(
        request,
        'accounts/placeholder.html',
        {
            'page_title': 'Create an Account',
            'message': 'Registration will be implemented in the accounts module.',
        },
    )


@login_required
def profile_placeholder(request):
    """Placeholder user profile hook for the teammate's accounts module."""
    return render(
        request,
        'accounts/placeholder.html',
        {
            'page_title': f'Profile — {request.user.username}',
            'message': 'User profile and order history will be implemented in the accounts module.',
        },
    )
