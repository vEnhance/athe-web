from django import forms

from .models import YearbookEntry


class YearbookEntryForm(forms.ModelForm):
    class Meta:
        model = YearbookEntry
        fields = [
            "display_name",
            "bio",
            "discord_username",
            "instagram_username",
            "github_username",
            "website_url",
        ]
        widgets = {
            "display_name": forms.TextInput(
                attrs={"placeholder": "How you want to be known"}
            ),
            "bio": forms.Textarea(
                attrs={
                    "placeholder": "Tell us about yourself!",
                    "rows": 5,
                    "maxlength": 1000,
                }
            ),
            "discord_username": forms.TextInput(
                attrs={"placeholder": "username or username#1234"}
            ),
            "instagram_username": forms.TextInput(attrs={"placeholder": "username"}),
            "github_username": forms.TextInput(attrs={"placeholder": "username"}),
            "website_url": forms.URLInput(attrs={"placeholder": "https://example.com"}),
        }
