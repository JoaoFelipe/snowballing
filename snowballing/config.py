"""This module configures the snowballing.

Please, use the database __init__ to replace these configurations.
"""
from pathlib import Path

# Database path
DATABASE_DIR = Path.home() / "database"

# Text editior path
TEXT_EDITOR = None
# Text editor argument for opening in a given line.
# Use a format string with arguments {year_path} and {line}
LINE_PARAMS = None

# List of possible work class tuples
# Each tuple has the follwing elements:
#   Class Name
#   Category name
#   Graph visibility (Options: display, hide, always_hide)
#   Graph node color
#   Graph node text color
CLASSES = [
    ("Work", "work", "display", "#FFD86E", "black"),
    ("WorkSnowball", "snowball", "display", "#6DCE9E", "white"),
    ("WorkOk", "ok", "display", "#68BDF6", "white"),
    ("WorkUnrelated", "unrelated", "hide", "#DE9BF9", "white"),
    ("WorkNoFile", "nofile", "hide", "#A5ABB6", "white"),
    ("WorkLang", "lang", "hide", "#ff8040", "white"),
    ("Site", "site", "hide", "#000080", "white"),
    ("Email", "site", "hide", "#000080", "white"),
]
# Default class for insertion
DEFAULT_CLASS = "Work"

# Similary Ratio for matching places
SIMILARITY_RATIO = 0.8

# Debug fields during BibTeX export
DEBUG_FIELDS = True

# List of exportable work fields to BibTeX
WORK_FIELDS = [
    "entrytype", "year", "name", "authors", "place",
    "booktitle", "bookauthors", "edition", "available",
    "volume", "number", "section", "pp", "article",
    "doi", "isbn",  "proceedings", "issn",
    "organization", "publisher", "school", "institution", "track",
    "ref", "local", "editors", "awards",
    "special", "website", "link", "scholar", "shorttitle", "address",
]

# Regexes that starts with ^ and ends with $
BIBTEX_IGNORE_FIELDS = [
    "excerpt", "month", "bookname", "url", "ID",

    # Tool
    "_.*", "force_.*", "file.*", "category", "alias", "aliases", "scholar_ok",
    "scholar", "cluster_id", "scholar_id", "display", "metakey", "due", "tyear",
    "citation_file", "notes", "tracking", "snowball", "request", "draw",
    "may_be_related_to", "ignore", "generate_title", "note",
]

# Map Work to BibTeX
WORK_BIBTEX_MAP = {
    "name": lambda x: "title",
    "authors": lambda x: "author",
    "local": lambda x: "address",
    "organization": lambda x: "publisher",
    "pp": lambda x: "pages",
    "entrytype": lambda x: "ENTRYTYPE",
    "place": lambda x: {
        "incollection": "booktitle",
        "inproceedings": "booktitle",
        "misc": "booktitle",
        "article": "journal",
        "book": "",
        "mastersthesis": "",
        "phdthesis": "",
        "techreport": "",
        "": ""
    }[getattr(x, "entrytype", "")]
}

# List of rows with form buttons (I suggest using no more than 4 per row)
# The form button is a tuple with two elements:
#   Label
#   Map of form widgets to value
FORM_BUTTONS = [
    [
        (
            "Ok", {
                "work_type_widget": "WorkOk",
                "file_field_widget": True,
            }
        ),
    ],
]

# List of text fields in forms
# Each tuple has 3 fields
#   Label
#   Work attribute
#   Widget variable (use none if you do not want a variable)
FORM_TEXT_FIELDS = [
    ("Related", "may_be_related_to", None),
    ("Display", "display", None),
    ("Link", "link", None),
]

# Module setting
MODULES = {
    'places': None,
    'work': None,
    'citations': None,
    'groups': None,
}
