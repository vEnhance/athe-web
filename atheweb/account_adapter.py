# Source - https://stackoverflow.com/a/29799664
# Posted by Mark Longair, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-20, License - CC BY-SA 3.0

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):  # type: ignore
        """
        Checks whether or not the site is open for signups.

        Next to simply returning True/False you can also intervene the
        regular flow by raising an ImmediateHttpResponse

        (Comment reproduced from the overridden method.)
        """
        return False


class PreservePasswordSocialAccountAdapter(DefaultSocialAccountAdapter):
    def authentication_inited(self, request, sociallogin):  # type: ignore
        """
        Called when email-based authentication is initiated.

        By default, allauth sets the password to unusable when connecting
        a social account via email authentication. We override this to
        preserve the user's existing password.
        """
        # Store the current password hash before allauth can change it
        user = sociallogin.user
        if user.pk:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                existing_user = User.objects.get(pk=user.pk)
                request._preserve_password = existing_user.password
            except User.DoesNotExist:
                pass

    def authentication_finished(self, request, sociallogin):  # type: ignore
        """
        Called when email-based authentication is finished.

        Restore the user's password if it was preserved.
        """
        if hasattr(request, "_preserve_password"):
            user = sociallogin.user
            if user.pk and user.password != request._preserve_password:
                user.password = request._preserve_password
                user.save(update_fields=["password"])
            del request._preserve_password
