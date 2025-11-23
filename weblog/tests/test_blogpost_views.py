import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory

from weblog.models import BlogPost
from weblog.views import (
    BlogPostCreateView,
    BlogPostDetailView,
    BlogPostLandingView,
    BlogPostListView,
    BlogPostUpdateView,
)


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def staff_user():
    """Create a staff user."""
    return User.objects.create_user(
        username="staffuser", password="testpass123", is_staff=True
    )


@pytest.fixture
def other_user():
    """Create another test user."""
    return User.objects.create_user(username="otheruser", password="testpass123")


@pytest.fixture
def published_post(user):
    """Create a published blog post."""
    return BlogPost.objects.create(
        title="Published Post",
        slug="published-post",
        display_author="Test Author",
        creator=user,
        content="Published content.",
        published=True,
    )


@pytest.fixture
def unpublished_post(user):
    """Create an unpublished blog post."""
    return BlogPost.objects.create(
        title="Draft Post",
        slug="draft-post",
        display_author="Test Author",
        creator=user,
        content="Draft content.",
        published=False,
    )


# ============================================================================
# BlogPostListView Tests
# ============================================================================


@pytest.mark.django_db
def test_blog_list_view_empty():
    """Test BlogPostListView with no posts."""
    factory = RequestFactory()
    request = factory.get("/blog/")
    request.user = AnonymousUser()
    response = BlogPostListView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_blog_list_view_shows_published(published_post):
    """Test BlogPostListView shows published posts."""
    factory = RequestFactory()
    request = factory.get("/blog/")
    request.user = AnonymousUser()
    response = BlogPostListView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["posts"].count() == 1
    assert published_post in response.context_data["posts"]


@pytest.mark.django_db
def test_blog_list_view_excludes_unpublished(unpublished_post):
    """Test BlogPostListView excludes unpublished posts."""
    factory = RequestFactory()
    request = factory.get("/blog/")
    request.user = AnonymousUser()
    response = BlogPostListView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["posts"].count() == 0


@pytest.mark.django_db
def test_blog_list_view_mixed(published_post, unpublished_post):
    """Test BlogPostListView with mixed published/unpublished."""
    factory = RequestFactory()
    request = factory.get("/blog/")
    request.user = AnonymousUser()
    response = BlogPostListView.as_view()(request)

    assert response.status_code == 200
    posts = response.context_data["posts"]
    assert posts.count() == 1
    assert published_post in posts
    assert unpublished_post not in posts


@pytest.mark.django_db
def test_blog_list_view_no_auth_required():
    """Test BlogPostListView is accessible without auth."""
    factory = RequestFactory()
    request = factory.get("/blog/")
    request.user = AnonymousUser()
    response = BlogPostListView.as_view()(request)

    assert response.status_code == 200


# ============================================================================
# BlogPostDetailView Tests
# ============================================================================


@pytest.mark.django_db
def test_blog_detail_view_published_anonymous(published_post):
    """Test anonymous user can view published post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{published_post.slug}/")
    request.user = AnonymousUser()
    response = BlogPostDetailView.as_view()(request, slug=published_post.slug)

    assert response.status_code == 200
    assert response.context_data["post"] == published_post


@pytest.mark.django_db
def test_blog_detail_view_unpublished_anonymous(unpublished_post):
    """Test anonymous user cannot view unpublished post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/")
    request.user = AnonymousUser()

    with pytest.raises(Exception):  # Should raise Http404
        BlogPostDetailView.as_view()(request, slug=unpublished_post.slug)


@pytest.mark.django_db
def test_blog_detail_view_unpublished_creator(user, unpublished_post):
    """Test creator can view their own unpublished post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/")
    request.user = user
    response = BlogPostDetailView.as_view()(request, slug=unpublished_post.slug)

    assert response.status_code == 200
    assert response.context_data["post"] == unpublished_post


@pytest.mark.django_db
def test_blog_detail_view_unpublished_other_user(other_user, unpublished_post):
    """Test other user cannot view someone else's unpublished post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/")
    request.user = other_user

    with pytest.raises(Exception):  # Should raise Http404
        BlogPostDetailView.as_view()(request, slug=unpublished_post.slug)


@pytest.mark.django_db
def test_blog_detail_view_unpublished_staff(staff_user, unpublished_post):
    """Test staff can view any unpublished post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/")
    request.user = staff_user
    response = BlogPostDetailView.as_view()(request, slug=unpublished_post.slug)

    assert response.status_code == 200
    assert response.context_data["post"] == unpublished_post


# ============================================================================
# BlogPostLandingView Tests
# ============================================================================


@pytest.mark.django_db
def test_blog_landing_view_requires_login():
    """Test BlogPostLandingView requires authentication."""
    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = AnonymousUser()
    response = BlogPostLandingView.as_view()(request)

    # LoginRequiredMixin redirects to login
    assert response.status_code == 302


@pytest.mark.django_db
def test_blog_landing_view_authenticated(user):
    """Test BlogPostLandingView works for authenticated user."""
    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_blog_landing_view_shows_pending_posts(user, unpublished_post):
    """Test landing view shows user's pending posts."""
    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert response.status_code == 200
    assert unpublished_post in response.context_data["pending_posts"]


@pytest.mark.django_db
def test_blog_landing_view_shows_published_posts(user, published_post):
    """Test landing view shows user's published posts."""
    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert response.status_code == 200
    assert published_post in response.context_data["published_posts"]


@pytest.mark.django_db
def test_blog_landing_view_can_create(user):
    """Test landing view allows creation when under limit."""
    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["can_create"] is True


@pytest.mark.django_db
def test_blog_landing_view_cannot_create_at_limit(user):
    """Test landing view disallows creation at 3 unpublished posts."""
    # Create 3 unpublished posts
    for i in range(3):
        BlogPost.objects.create(
            title=f"Draft {i}",
            slug=f"draft-{i}",
            display_author="Author",
            creator=user,
            content="Content.",
            published=False,
        )

    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["can_create"] is False


@pytest.mark.django_db
def test_blog_landing_view_only_shows_own_posts(user, other_user):
    """Test landing view only shows the current user's posts."""
    # Create posts for both users
    own_post = BlogPost.objects.create(
        title="Own Post",
        slug="own-post",
        display_author="Author",
        creator=user,
        content="Content.",
    )
    other_post = BlogPost.objects.create(
        title="Other Post",
        slug="other-post",
        display_author="Author",
        creator=other_user,
        content="Content.",
    )

    factory = RequestFactory()
    request = factory.get("/blog/my/")
    request.user = user
    response = BlogPostLandingView.as_view()(request)

    assert own_post in response.context_data["pending_posts"]
    assert other_post not in response.context_data["pending_posts"]


# ============================================================================
# BlogPostCreateView Tests
# ============================================================================


@pytest.mark.django_db
def test_blog_create_view_requires_login():
    """Test BlogPostCreateView requires authentication."""
    factory = RequestFactory()
    request = factory.get("/blog/create/")
    request.user = AnonymousUser()
    response = BlogPostCreateView.as_view()(request)

    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_blog_create_view_get(user):
    """Test BlogPostCreateView GET shows form."""
    factory = RequestFactory()
    request = factory.get("/blog/create/")
    request.user = user
    response = BlogPostCreateView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_blog_create_view_blocked_at_limit(user, client):
    """Test BlogPostCreateView is blocked when user has 3 unpublished posts."""
    # Create 3 unpublished posts
    for i in range(3):
        BlogPost.objects.create(
            title=f"Draft {i}",
            slug=f"draft-{i}",
            display_author="Author",
            creator=user,
            content="Content.",
            published=False,
        )

    client.force_login(user)
    response = client.get("/blog/create/")

    assert response.status_code == 302  # Redirected away


@pytest.mark.django_db
def test_blog_create_view_allowed_with_published(user):
    """Test user can create when they have 3 published posts."""
    # Create 3 published posts
    for i in range(3):
        BlogPost.objects.create(
            title=f"Published {i}",
            slug=f"published-{i}",
            display_author="Author",
            creator=user,
            content="Content.",
            published=True,
        )

    factory = RequestFactory()
    request = factory.get("/blog/create/")
    request.user = user
    response = BlogPostCreateView.as_view()(request)

    assert response.status_code == 200  # Can still create


# ============================================================================
# BlogPostUpdateView Tests
# ============================================================================


@pytest.mark.django_db
def test_blog_update_view_requires_login(unpublished_post, client):
    """Test BlogPostUpdateView requires authentication."""
    response = client.get(f"/blog/{unpublished_post.slug}/edit/")

    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_blog_update_view_creator_can_edit(user, unpublished_post):
    """Test creator can access update view for unpublished post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/edit/")
    request.user = user
    response = BlogPostUpdateView.as_view()(request, slug=unpublished_post.slug)

    assert response.status_code == 200


@pytest.mark.django_db
def test_blog_update_view_other_user_denied(other_user, unpublished_post):
    """Test other user cannot edit someone else's post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{unpublished_post.slug}/edit/")
    request.user = other_user

    with pytest.raises(Exception):  # Should raise Http404
        BlogPostUpdateView.as_view()(request, slug=unpublished_post.slug)


@pytest.mark.django_db
def test_blog_update_view_published_denied(user, published_post):
    """Test creator cannot edit published post."""
    factory = RequestFactory()
    request = factory.get(f"/blog/{published_post.slug}/edit/")
    request.user = user

    with pytest.raises(Exception):  # Should raise Http404
        BlogPostUpdateView.as_view()(request, slug=published_post.slug)
