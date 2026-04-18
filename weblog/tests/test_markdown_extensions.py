from atheweb.validators import VALIDATOR_WITH_FIGURES
from markdownfield.rendering import render_markdown


def render(md: str) -> str:
    return render_markdown(md, VALIDATOR_WITH_FIGURES)


def test_figure_standalone_image_with_alt():
    result = render("![A caption](https://example.com/img.png)")
    assert "<figure>" in result
    assert "<figcaption>A caption</figcaption>" in result
    assert 'href="https://example.com/img.png"' in result
    assert 'alt="A caption"' in result


def test_figure_no_figure_without_alt():
    result = render("![](https://example.com/img.png)")
    assert "<figure>" not in result
    assert "<img" in result


def test_figure_preserves_title():
    result = render('![Caption](https://example.com/img.png "My Title")')
    assert 'title="My Title"' in result
    assert "<figcaption>Caption</figcaption>" in result


def test_figure_inline_image_not_wrapped():
    result = render("Text with ![alt](https://example.com/img.png) inline.")
    assert "<figure>" not in result
    assert "<img" in result


def test_figure_link_opens_in_new_tab():
    result = render("![Caption](https://example.com/img.png)")
    assert 'target="_blank"' in result
    assert "noopener" in result


# Math rendering - $...$ is passed through as literal text for MathJax to process
# client-side. CommonMark's stricter emphasis rules mean underscores inside
# $...$ are never mangled, so no server-side math plugin is needed.


def test_math_inline_preserved():
    result = render("$x^2$")
    assert "$x^2$" in result
    assert "<em>" not in result


def test_math_display_preserved():
    result = render("$$\\int_0^1 x\\,dx$$")
    assert "$$" in result
    assert "\\int_0^1" in result


def test_math_underscores_not_italicised():
    result = render("$a_1 + a_2$")
    assert "<em>" not in result
    assert "$a_1 + a_2$" in result


def test_math_in_footnote():
    result = render("See[^1]\n\n[^1]: Value is $x^2$")
    assert "$x^2$" in result
    assert "<em>" not in result
