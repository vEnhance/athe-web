from markdownfield.validators import MARKDOWN_ATTRS, MARKDOWN_TAGS, Validator

assert isinstance(MARKDOWN_TAGS, set)

VALIDATOR_WITH_FIGURES = Validator(
    allowed_tags=MARKDOWN_TAGS.union({"figure", "figcaption"}),
    allowed_attrs={**MARKDOWN_ATTRS, "*": {"id", "class"}},
)
