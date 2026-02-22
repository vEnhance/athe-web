"""Markdown extension to protect LaTeX math from markdown processing.

Protects $...$ (inline), $$...$$ (display), \\(...\\) and \\[...\\]
delimiters by stashing them before markdown processes the text,
then restoring them afterward. This prevents markdown from interpreting
special characters like _ and * inside math expressions.
"""

import re

from markdown import Extension
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor

# Sentinel characters unlikely to appear in normal text
MATH_PLACEHOLDER = "\x02MATHBLOCK%d\x03"


class MathPreprocessor(Preprocessor):
    """Replace math delimiters with placeholders before markdown processing."""

    def run(self, lines: list[str]) -> list[str]:
        text = "\n".join(lines)
        self.md._math_stash: list[str] = []  # type: ignore[attr-defined]

        def stash(m: re.Match[str]) -> str:
            idx = len(self.md._math_stash)  # type: ignore[attr-defined]
            self.md._math_stash.append(m.group(0))  # type: ignore[attr-defined]
            return MATH_PLACEHOLDER % idx

        # Display math: $$...$$ (including multiline)
        text = re.sub(r"\$\$(.*?)\$\$", stash, text, flags=re.DOTALL)
        # Inline math: $...$ (not preceded/followed by $)
        text = re.sub(r"(?<!\$)\$(?!\$)((?:[^$\\]|\\.)+?)\$(?!\$)", stash, text)
        # Display math: \[...\]
        text = re.sub(r"\\\[(.*?)\\\]", stash, text, flags=re.DOTALL)
        # Inline math: \(...\)
        text = re.sub(r"\\\((.*?)\\\)", stash, text)

        return text.split("\n")


class MathPostprocessor(Postprocessor):
    """Restore math delimiters after markdown processing."""

    def run(self, text: str) -> str:
        stash: list[str] = getattr(self.md, "_math_stash", [])
        for i, math in enumerate(stash):
            text = text.replace(MATH_PLACEHOLDER % i, math)
        return text


class MathExtension(Extension):
    """Extension to protect LaTeX math from markdown processing."""

    def extendMarkdown(self, md) -> None:  # type: ignore[override]
        md.preprocessors.register(MathPreprocessor(md), "math_protect", 200)
        md.postprocessors.register(MathPostprocessor(md), "math_restore", 200)


def makeExtension(**kwargs) -> MathExtension:  # type: ignore[no-untyped-def]
    """Create the extension."""
    return MathExtension(**kwargs)
