import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone


class InviteLink(models.Model):
    """A shareable, expiring link that lets someone claim an existing record."""

    #: URL name this kind of invite is served at.
    url_name: str

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        help_text="A descriptive name for this invite link, e.g. 'Spring 2025'",
    )
    expiration_date = models.DateTimeField(
        help_text="Date and time when this invite link expires"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def is_expired(self) -> bool:
        """Check if this invite link has expired."""
        return timezone.now() > self.expiration_date

    def get_absolute_url(self) -> str:
        """Get the URL for this invite link."""
        return reverse(self.url_name, kwargs={"invite_id": self.id})


class StaffInviteLink(InviteLink):
    """
    An invite link for staff members to register and connect to their StaffPhotoListing.
    """

    url_name = "reg:add-staff"

    class Meta(InviteLink.Meta):
        verbose_name = "Staff Invite Link"
        verbose_name_plural = "Staff Invite Links"

    def __str__(self) -> str:
        return (
            f"{self.name} (expires {self.expiration_date.strftime('%Y-%m-%d %H:%M')})"
        )


class StudentInviteLink(InviteLink):
    """
    An invite link for students to register and connect to their Student record.
    """

    url_name = "reg:add-student"

    semester = models.ForeignKey(
        "courses.Semester",
        on_delete=models.CASCADE,
        related_name="invite_links",
        help_text="The semester this invite link is for",
    )

    class Meta(InviteLink.Meta):
        verbose_name = "Student Invite Link"
        verbose_name_plural = "Student Invite Links"

    def __str__(self) -> str:
        return (
            f"{self.name} - {self.semester} "
            f"(expires {self.expiration_date.strftime('%Y-%m-%d %H:%M')})"
        )

    def is_semester_ended(self) -> bool:
        """Check if the semester has ended."""
        return timezone.localdate() > self.semester.end_date


class StudentRegistration(models.Model):
    """A student's answers to the start-of-semester questionnaire.

    Filled in on the invite link, right after the student claims their name.
    Its whole purpose is to be exported for the class matching, so the fields
    mirror the questions asked rather than anything the site itself renders.
    """

    class Challenge(models.TextChoices):
        PLAN = "plan", "I make a plan and act accordingly"
        BIG_PICTURE = (
            "big_picture",
            "I think about the bigger picture and act with intention",
        )
        CREATIVE = "creative", "I look for creative and unique angles"
        CONSULT = (
            "consult",
            "I consult other people and make sure everyone's on the same page",
        )
        WING_IT = "wing_it", "I wing it and trust something fun will happen"

    class Value(models.TextChoices):
        CLARITY = "clarity", "Clarity and harmony"
        FLEXIBILITY = "flexibility", "Flexibility and space"
        VISION = "vision", "Long-term vision and clear goals"
        VIBES = "vibes", "Good vibes and spontaneity"
        CONNECTION = "connection", "Connection and support"

    class Compass(models.TextChoices):
        LOGIC = "logic", "Logic"
        CURIOSITY = "curiosity", "Curiosity"
        EMPATHY = "empathy", "Empathy"
        VIBES = "vibes", "Vibes"
        VALUES = "values", "Personal values"

    class DayOff(models.TextChoices):
        PRODUCTIVE = "productive", "Getting things done, then relaxing"
        EXPLORING = "exploring", "Exploring new places or hobbies"
        REFLECTING = "reflecting", "Reflecting or diving into something meaningful"
        SPONTANEOUS = "spontaneous", "Doing whatever feels good in the moment"
        SOCIAL = "social", "Connecting with friends"

    class FriendSays(models.TextChoices):
        SUPPORTIVE = "supportive", "Sensitive and supportive"
        UPLIFTING = "uplifting", "Fun and uplifting"
        IMAGINATIVE = "imaginative", "Imaginative and adaptable"
        TRUSTWORTHY = "trustworthy", "Trustworthy and honest"
        THOUGHTFUL = "thoughtful", "Thoughtful and purposeful"

    student = models.OneToOneField(
        "courses.Student",
        on_delete=models.CASCADE,
        related_name="registration",
    )
    completed_steps = models.JSONField(
        default=list,
        blank=True,
        help_text="Slugs of the questionnaire pages this student has saved. "
        "The questionnaire is filled in a page at a time, so a registration "
        "missing some of these was abandoned partway.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Demographic info
    email = models.EmailField(
        help_text="Email you check regularly; "
        "this is the primary email you will receive notifications through"
    )
    parent_email = models.EmailField(
        help_text="A parent or guardian's email, for payment purposes"
    )
    discord_username = models.CharField(
        max_length=64, help_text="Your Discord username, e.g. mathlover42"
    )
    taken_class_before = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether the student has taken an Athemath class before",
    )

    # Class selection; the top three picks and the "rather not" pile both live
    # in CoursePreference
    subject_interest = models.JSONField(
        default=dict,
        blank=True,
        help_text="How interested the student is in each subject, "
        "e.g. {'algebra': 'very', ...}",
    )
    difficulty_levels = models.JSONField(
        default=list,
        blank=True,
        help_text="Difficulty bands the student would be happy in, "
        "e.g. ['aime', 'olympiad']",
    )
    course_comments = models.TextField(
        blank=True, help_text="Anything else to say about class preferences"
    )

    # Availability
    availability = models.JSONField(
        default=list,
        help_text="Slot keys the student is available for, e.g. ['sat-0830', ...]",
    )
    availability_comments = models.TextField(
        blank=True, help_text="Anything else to say about availability"
    )

    # Sorting ceremony
    quiz_challenge = models.CharField(
        max_length=20,
        choices=Challenge,
        verbose_name="How do you usually approach a challenge?",
    )
    quiz_values = models.CharField(
        max_length=20,
        choices=Value,
        verbose_name="What do you value most when working with others?",
    )
    quiz_compass = models.CharField(
        max_length=20,
        choices=Compass,
        verbose_name="When making a decision, what guides you most?",
    )
    quiz_day_off = models.CharField(
        max_length=20,
        choices=DayOff,
        verbose_name="What's your ideal way to spend a day off?",
    )
    quiz_friend = models.CharField(
        max_length=20,
        choices=FriendSays,
        verbose_name="How would a close friend describe you?",
    )
    house_request = models.TextField(
        blank=True,
        verbose_name="Do you have any preferences for what house "
        "you'd like to be sorted in?",
    )

    class Meta:
        verbose_name = "Student Registration"
        verbose_name_plural = "Student Registrations"
        ordering = ("student",)

    def __str__(self) -> str:
        return f"Registration for {self.student}"

    def mark_complete(self, step: str) -> None:
        """Record that a page has been saved. Caller still has to save()."""
        if step not in self.completed_steps:
            self.completed_steps = [*self.completed_steps, step]

    def quiz_answers(self) -> dict[str, str]:
        """The five sorting questions, as ``{field name: stored choice}``."""
        return {
            field: getattr(self, field)
            for field in (
                "quiz_challenge",
                "quiz_values",
                "quiz_compass",
                "quiz_day_off",
                "quiz_friend",
            )
        }


class CoursePreference(models.Model):
    """One student's opinion of one class: a top-three pick, or a hard no.

    Only classes the student said something about get a row. Ranking a whole
    catalogue is miserable and the answers below fourth place say very little,
    so a class with no row here is simply one the student is neutral about.
    """

    registration = models.ForeignKey(
        StudentRegistration,
        on_delete=models.CASCADE,
        related_name="course_preferences",
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="preferences"
    )
    rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="1, 2 or 3 for the student's first, second and third choice; "
        "blank when excluded",
    )
    excluded = models.BooleanField(
        default=False,
        help_text="Set when the student does not want to take this class at all",
    )

    class Meta:
        verbose_name = "Course Preference"
        verbose_name_plural = "Course Preferences"
        constraints = (
            models.UniqueConstraint(
                fields=["registration", "course"],
                name="unique_course_per_registration",
            ),
        )
        # Wanted classes first, best-ranked first; the excluded pile trails.
        ordering = ("excluded", "rank", "course__name")

    def __str__(self) -> str:
        if self.excluded:
            return f"{self.course.name}: excluded"
        return f"{self.course.name}: #{self.rank}"
