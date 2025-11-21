from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from courses.models import Student
from home.models import StaffPhotoListing


class StaffSelectionForm(forms.Form):
    """Form for selecting which StaffPhotoListing the user corresponds to."""

    staff_listing = forms.ModelChoiceField(
        queryset=StaffPhotoListing.objects.exclude(category="xstaff"),
        widget=forms.RadioSelect,
        label="Who are you?",
        help_text="Please select which staff member you are from the list below.",
    )


class StaffRegistrationForm(UserCreationForm):
    """Form for creating a new staff user account."""

    email = forms.EmailField(
        required=True,
        help_text="Required. Enter your email address.",
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        help_text="Required. Enter your first name.",
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        help_text="Required. Enter your last name.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes and help text
        self.fields[
            "username"
        ].help_text = (
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        )
        self.fields[
            "password1"
        ].help_text = "Your password must contain at least 8 characters and can't be entirely numeric."
        self.fields[
            "password2"
        ].help_text = "Enter the same password as before, for verification."


class LoginChoiceForm(forms.Form):
    """Form for choosing whether to login or create a new account."""

    HAS_ACCOUNT_CHOICES = [
        ("yes", "Yes, I have an account from a previous year and will log in"),
        ("no", "No, I am joining Athemath for the first time"),
    ]

    has_account = forms.ChoiceField(
        choices=HAS_ACCOUNT_CHOICES,
        widget=forms.RadioSelect,
        label="Do you already have an account from a previous Athemath?",
        help_text="Select whether you have an existing account or need to create a new one.",
    )


class StudentRegistrationForm(UserCreationForm):
    """Form for creating a new student user account."""

    class Meta:
        model = User
        fields = [
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
        ]

    def __init__(self, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)
        # Add help text
        self.fields[
            "username"
        ].help_text = (
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        )
        self.fields[
            "password1"
        ].help_text = "Your password must contain at least 8 characters and can't be entirely numeric."
        self.fields[
            "password2"
        ].help_text = "Enter the same password as before, for verification."


class StudentSelectionForm(forms.Form):
    """Form for selecting which Student record the user corresponds to."""

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),  # Will be set in __init__
        widget=forms.RadioSelect,
        label="Who are you?",
        help_text="Please select your name from the roster below.",
    )

    def __init__(self, semester, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)
        # Only show students from this semester
        self.fields["student"].queryset = Student.objects.filter(  # type: ignore
            semester=semester
        )
