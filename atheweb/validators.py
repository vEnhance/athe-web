from markdownfield.validators import Validator, MARKDOWN_TAGS, MARKDOWN_ATTRS

VALIDATOR_WITH_FIGURES = Validator(
    allowed_tags=MARKDOWN_TAGS + ["figure", "figcaption"],
    allowed_attrs=MARKDOWN_ATTRS,
)
