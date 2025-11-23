from datetime import date

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from weblog.models import BlogPost


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def other_user():
    """Create another test user."""
    return User.objects.create_user(username="otheruser", password="testpass123")


# ============================================================================
# BlogPost Model Tests
# ============================================================================


@pytest.mark.django_db
def test_blogpost_creation(user):
    """Test creating a BlogPost model."""
    post = BlogPost.objects.create(
        title="My First Post",
        subtitle="A great subtitle",
        slug="my-first-post",
        display_author="John Doe",
        creator=user,
        content="This is my first blog post content.",
    )
    assert post.title == "My First Post"
    assert post.subtitle == "A great subtitle"
    assert post.slug == "my-first-post"
    assert post.display_author == "John Doe"
    assert post.creator == user
    assert post.id is not None
    assert post.created_at is not None
    assert post.updated_at is not None


@pytest.mark.django_db
def test_blogpost_str(user):
    """Test the string representation of BlogPost."""
    post = BlogPost.objects.create(
        title="Test Post Title",
        slug="test-post",
        display_author="Author",
        creator=user,
        content="Content.",
    )
    assert str(post) == "Test Post Title"


@pytest.mark.django_db
def test_blogpost_default_published_false(user):
    """Test that BlogPost is unpublished by default."""
    post = BlogPost.objects.create(
        title="Draft Post",
        slug="draft-post",
        display_author="Author",
        creator=user,
        content="Draft content.",
    )
    assert post.published is False


@pytest.mark.django_db
def test_blogpost_default_display_date(user):
    """Test that BlogPost display_date defaults to today."""
    post = BlogPost.objects.create(
        title="Post Today",
        slug="post-today",
        display_author="Author",
        creator=user,
        content="Content.",
    )
    assert post.display_date == date.today()


@pytest.mark.django_db
def test_blogpost_custom_display_date(user):
    """Test that BlogPost can have a custom display_date."""
    custom_date = date(2023, 5, 15)
    post = BlogPost.objects.create(
        title="Old Post",
        slug="old-post",
        display_author="Author",
        creator=user,
        content="Content.",
        display_date=custom_date,
    )
    assert post.display_date == custom_date


@pytest.mark.django_db
def test_blogpost_slug_unique(user):
    """Test that BlogPost slugs must be unique."""
    BlogPost.objects.create(
        title="First Post",
        slug="unique-slug",
        display_author="Author",
        creator=user,
        content="First content.",
    )

    with pytest.raises(IntegrityError):
        BlogPost.objects.create(
            title="Second Post",
            slug="unique-slug",
            display_author="Author",
            creator=user,
            content="Second content.",
        )


@pytest.mark.django_db
def test_blogpost_subtitle_optional(user):
    """Test that BlogPost subtitle is optional."""
    post = BlogPost.objects.create(
        title="No Subtitle",
        slug="no-subtitle",
        display_author="Author",
        creator=user,
        content="Content.",
    )
    assert post.subtitle == ""


@pytest.mark.django_db
def test_blogpost_published_true(user):
    """Test creating a published BlogPost."""
    post = BlogPost.objects.create(
        title="Published Post",
        slug="published-post",
        display_author="Author",
        creator=user,
        content="Content.",
        published=True,
    )
    assert post.published is True


@pytest.mark.django_db
def test_blogpost_get_absolute_url(user):
    """Test the get_absolute_url method."""
    post = BlogPost.objects.create(
        title="URL Test",
        slug="url-test-post",
        display_author="Author",
        creator=user,
        content="Content.",
    )
    assert post.get_absolute_url() == "/weblog/blog/url-test-post/"


@pytest.mark.django_db
def test_blogpost_ordering(user):
    """Test that blog posts are ordered by display_date descending."""
    post1 = BlogPost.objects.create(
        title="Older Post",
        slug="older-post",
        display_author="Author",
        creator=user,
        content="Older content.",
        display_date=date(2023, 1, 1),
    )
    post2 = BlogPost.objects.create(
        title="Newer Post",
        slug="newer-post",
        display_author="Author",
        creator=user,
        content="Newer content.",
        display_date=date(2023, 6, 1),
    )

    posts = list(BlogPost.objects.all())
    # Most recent first
    assert posts[0].id == post2.id
    assert posts[1].id == post1.id


@pytest.mark.django_db
def test_blogpost_markdown_rendering(user):
    """Test that markdown content is rendered to HTML."""
    post = BlogPost.objects.create(
        title="Markdown Test",
        slug="markdown-test",
        display_author="Author",
        creator=user,
        content="**Bold text** and *italic text*",
    )
    # The content_rendered field should contain HTML
    assert "<strong>" in post.content_rendered or "<b>" in post.content_rendered
    assert "<em>" in post.content_rendered or "<i>" in post.content_rendered


@pytest.mark.django_db
def test_blogpost_multiple_creators(user, other_user):
    """Test that different users can create posts with different slugs."""
    post1 = BlogPost.objects.create(
        title="User 1 Post",
        slug="post-1",
        display_author="User One",
        creator=user,
        content="Content by user 1.",
    )
    post2 = BlogPost.objects.create(
        title="User 2 Post",
        slug="post-2",
        display_author="User Two",
        creator=other_user,
        content="Content by user 2.",
    )

    assert post1.creator == user
    assert post2.creator == other_user
    assert BlogPost.objects.count() == 2


@pytest.mark.django_db
def test_blogpost_related_name(user):
    """Test that user can access their posts via related_name."""
    BlogPost.objects.create(
        title="Post 1",
        slug="post-1",
        display_author="Author",
        creator=user,
        content="Content 1.",
    )
    BlogPost.objects.create(
        title="Post 2",
        slug="post-2",
        display_author="Author",
        creator=user,
        content="Content 2.",
    )

    assert user.blog_posts.count() == 2
