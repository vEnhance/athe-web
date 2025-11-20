# Source - https://stackoverflow.com/a/29799664
# Posted by Mark Longair, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-20, License - CC BY-SA 3.0

from allauth.account.adapter import DefaultAccountAdapter


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):  # type: ignore
        """
        Checks whether or not the site is open for signups.

        Next to simply returning True/False you can also intervene the
        regular flow by raising an ImmediateHttpResponse

        (Comment reproduced from the overridden method.)
        """
        return False
