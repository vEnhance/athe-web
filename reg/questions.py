"""The fixed option lists behind the class-preference questions.

Kept as plain data rather than model choices because the answers are stored in
JSON fields: adding a subject or a difficulty band is an edit here and nothing
else. The matching is done by hand (or by an LLM) from the exported answers, so
these only have to be meaningful to a reader, not to a solver.
"""

#: Subjects students rate their interest in, in the order the grid shows them.
SUBJECTS: tuple[tuple[str, str], ...] = (
    ("algebra", "Algebra"),
    ("combinatorics", "Combinatorics"),
    ("geometry", "Geometry"),
    ("number_theory", "Number Theory"),
)

#: How interested a student can be in a subject, best first.
INTEREST_LEVELS: tuple[tuple[str, str], ...] = (
    ("very", "Very interested"),
    ("somewhat", "Somewhat interested"),
    ("not", "Not interested"),
)

#: Difficulty bands a class can sit in, easiest first.
DIFFICULTY_LEVELS: tuple[tuple[str, str], ...] = (
    ("amc", "AMC"),
    ("amc_mid_aime", "AMC - Mid AIME"),
    ("aime", "AIME"),
    ("aime_beginner_olympiad", "AIME - Beginner Olympiad"),
    ("late_aime_mid_olympiad", "Late AIME - Mid Olympiad"),
    ("olympiad", "Olympiad"),
    ("unsure", "I don't know"),
)

#: Explains the bands above to students who did not grow up with the AMC.
DIFFICULTY_HELP = (
    "If you're not familiar with the U.S. system: AMC means computational "
    "problems done quickly (25 problems in 75 minutes), AIME means "
    "computational problems that are harder and more involved (15 problems in "
    "3 hours), and Olympiad means proof problems."
)

SUBJECT_KEYS = frozenset(key for key, _ in SUBJECTS)
INTEREST_KEYS = frozenset(key for key, _ in INTEREST_LEVELS)
DIFFICULTY_KEYS = frozenset(key for key, _ in DIFFICULTY_LEVELS)
