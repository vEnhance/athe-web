"""Markdown-it-py plugins for weblog."""

from html import escape

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin as _dollarmath_plugin


def dollarmath_plugin(md: MarkdownIt) -> None:
    # double_inline treats $$...$$ as inline math in inline contexts (e.g. footnotes)
    _dollarmath_plugin(md, double_inline=True)


def figure_plugin(md: MarkdownIt) -> None:
    md.core.ruler.push("figure_caption", _figure_caption_rule)


def _figure_caption_rule(state: StateCore) -> None:
    i = 0
    while i < len(state.tokens):
        if (
            i + 2 < len(state.tokens)
            and state.tokens[i].type == "paragraph_open"
            and state.tokens[i + 1].type == "inline"
            and state.tokens[i + 2].type == "paragraph_close"
        ):
            inline = state.tokens[i + 1]
            children = inline.children or []
            if len(children) == 1 and children[0].type == "image":
                img = children[0]
                alt_text = "".join(
                    c.content for c in (img.children or []) if c.type == "text"
                )
                src = str(img.attrGet("src") or "")
                title_raw = img.attrGet("title")
                title = str(title_raw) if title_raw is not None else None

                if alt_text:
                    e_src = escape(src, quote=True)
                    e_alt = escape(alt_text, quote=True)
                    title_attr = (
                        f' title="{escape(title, quote=True)}"' if title else ""
                    )
                    html = (
                        f"<figure>"
                        f'<a href="{e_src}" target="_blank" rel="noopener">'
                        f'<img src="{e_src}" alt="{e_alt}"{title_attr}>'
                        f"</a>"
                        f"<figcaption>{e_alt}</figcaption>"
                        f"</figure>\n"
                    )
                    figure_token = Token("html_block", "", 0)
                    figure_token.content = html
                    figure_token.map = state.tokens[i].map
                    state.tokens[i : i + 3] = [figure_token]
                    continue
        i += 1
