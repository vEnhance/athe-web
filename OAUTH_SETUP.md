# OAuth Authentication Setup

This document explains how to configure Google and GitHub OAuth authentication for the athe-web application.

## Overview

The application uses `django-allauth` to support authentication via:
- **Google OAuth** (primary, emphasized)
- **GitHub OAuth** (primary, emphasized)
- **Username/Password** (fallback, de-emphasized)

## Initial Setup

After installing dependencies and running migrations, you need to configure OAuth applications for Google and GitHub.

### 1. Configure Django Sites Framework

First, update the site domain in the Django admin or via shell:

```bash
uv run python manage.py shell
```

Then in the Python shell:

```python
from django.contrib.sites.models import Site
site = Site.objects.get_current()
site.domain = 'localhost:8000'  # For development
site.name = 'Athemath Local'
site.save()
```

For production, use your actual domain (e.g., `athemath.org`).

### 2. Set Up Google OAuth

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google+ API

2. **Create OAuth 2.0 Credentials:**
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Web application"
   - Authorized redirect URIs:
     - Development: `http://localhost:8000/accounts/google/login/callback/`
     - Production: `https://your-domain.com/accounts/google/login/callback/`

3. **Add Credentials to Django Admin:**
   - Start the development server: `make runserver`
   - Go to `http://localhost:8000/admin/`
   - Navigate to "Social applications" under "Social Accounts"
   - Click "Add social application"
   - Provider: Google
   - Name: Google OAuth
   - Client id: (paste from Google Cloud Console)
   - Secret key: (paste from Google Cloud Console)
   - Sites: Select your site (localhost:8000 or your domain)
   - Save

### 3. Set Up GitHub OAuth

1. **Create a GitHub OAuth App:**
   - Go to [GitHub Developer Settings](https://github.com/settings/developers)
   - Click "New OAuth App"
   - Application name: Athemath (or your app name)
   - Homepage URL:
     - Development: `http://localhost:8000`
     - Production: `https://your-domain.com`
   - Authorization callback URL:
     - Development: `http://localhost:8000/accounts/github/login/callback/`
     - Production: `https://your-domain.com/accounts/github/login/callback/`

2. **Add Credentials to Django Admin:**
   - Go to `http://localhost:8000/admin/`
   - Navigate to "Social applications" under "Social Accounts"
   - Click "Add social application"
   - Provider: GitHub
   - Name: GitHub OAuth
   - Client id: (paste from GitHub)
   - Secret key: (paste from GitHub)
   - Sites: Select your site
   - Save

## Testing

1. Start the development server:
   ```bash
   make runserver
   ```

2. Navigate to `http://localhost:8000/login/`

3. You should see:
   - Prominent "Continue with Google" button (red/danger style)
   - Prominent "Continue with GitHub" button (dark style)
   - A divider with "or use username/password"
   - A de-emphasized traditional login form

4. Click on a social login button and test the authentication flow

## Configuration Details

### Settings (atheweb/settings.py)

Key configuration settings:

```python
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
```

### How It Works

1. **New Users:** When a user signs in with Google/GitHub for the first time:
   - Their account is automatically created
   - Email is fetched from the OAuth provider
   - They are logged in immediately

2. **Existing Users:** If a user's email matches an existing account:
   - The social account is automatically connected to their existing account
   - They can use either social login or username/password

3. **Fallback:** Users without Google/GitHub access can still use username/password

## Production Considerations

1. **Environment Variables:** For production, consider using environment variables for OAuth secrets:
   ```python
   import os
   SOCIALACCOUNT_PROVIDERS = {
       "google": {
           "APP": {
               "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
               "secret": os.getenv("GOOGLE_SECRET", ""),
           },
       },
       # ...
   }
   ```

2. **HTTPS:** Always use HTTPS in production for OAuth callbacks

3. **Domain Configuration:** Update the Site domain to match your production domain

## Troubleshooting

### "Social application not found" error
- Ensure you've added the social application in Django admin
- Verify the provider name matches exactly (case-sensitive)
- Check that your site is selected in the social application

### Redirect URI mismatch
- Verify the callback URL in your OAuth provider settings matches exactly
- Include the trailing slash: `/accounts/google/login/callback/`

### Email conflicts
- If auto-connection fails, users may need to verify their email
- Check `ACCOUNT_EMAIL_VERIFICATION` setting

## Additional Resources

- [django-allauth Documentation](https://docs.allauth.org/)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
