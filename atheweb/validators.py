from markdownfield.validators import Validator, MARKDOWN_TAGS, MARKDOWN_ATTRS

assert isinstance(MARKDOWN_TAGS, set)

VALIDATOR_WITH_FIGURES = Validator(
    allowed_tags=MARKDOWN_TAGS.union({"figure", "figcaption"}),
    allowed_attrs={**MARKDOWN_ATTRS, "*": {"id", "class"}},
)
