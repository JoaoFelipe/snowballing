from pathlib import Path
from snowballing import config
from . import places, work, citations, groups

### Database path. Do not change it unless you know what you are doing
config.DATABASE_DIR = Path(__file__).parent.resolve()

### Text editior path
config.TEXT_EDITOR = "C:\\Program Files\\Sublime Text 3\\sublime_text.exe"
### Text editor argument for opening in a given line.
### Use a format string with arguments {year_path} and {line}
config.LINE_PARAMS = "{year_path}:{line}"

### List of possible work class tuples
### Each tuple has the follwing elements:
###   Class Name
###   Category name
###   Graph visibility (Options: display, hide, always_hide)
###   Graph node color
###   Graph node text color
config.CLASSES = [
    ("Work", "work", "display", "#FFD86E", "black"),
    ("WorkSnowball", "snowball", "display", "#6DCE9E", "white"),
    ("WorkOk", "ok", "display", "#68BDF6", "white"),
    ("WorkUnrelated", "unrelated", "hide", "#DE9BF9", "white"),
    ("WorkNoFile", "nofile", "hide", "#A5ABB6", "white"),
    ("WorkLang", "lang", "hide", "#ff8040", "white"),
    ("Site", "site", "hide", "#000080", "white"),
    ("Email", "site", "hide", "#000080", "white"),
]
### Default class for insertion
config.DEFAULT_CLASS = "Work"

### Similary Ration for matching places
config.SIMILARITY_RATIO = 0.8

### Debug fields during BibTeX export
config.DEBUG_FIELDS = True

### List of exportable work fields to BibTeX
config.WORK_FIELDS = [
    "entrytype", "year", "name", "authors", "place",
    "booktitle", "bookauthors", "edition", "available",
    "volume", "number", "section", "pp", "article",
    "doi", "isbn",  "proceedings", "issn",
    "organization", "publisher", "school", "institution", "track",
    "ref", "local", "editors", "awards",
    "special", "website", "link", "scholar", "shorttitle", "address",
]

### Ignore fields when exporting to BibTeX
### Regexes that starts with ^ and ends with $
config.BIBTEX_IGNORE_FIELDS = [
    "excerpt", "month", "bookname", "url", "ID", 

    # Tool
    "_.*", "force_.*", "file.*", "category", "alias", "aliases", "scholar_ok",
    "scholar", "cluster_id", "scholar_id", "display", "metakey", "due", "tyear",
    "citation_file", "notes", "tracking", "snowball", "may_be_related_to", 

    # Extra
    "request",
    "arxiv",
    "summary",  "approach_name", 
    "draw", "ignore", "generate_title", "star", "evaluation", "export",
    "resumo", "star2",  "scholar_id2", "see",
    "define", "summarization", "visualization", "categories", "todo",
    "tool_summary", "collection", "lab", "note", "query", "storage",
    "acm",  
]

### Map Work to BibTeX
config.WORK_BIBTEX_MAP = {
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

### List of rows with form buttons (I suggest using no more than 4 per row)
### The form button is a tuple with two elements:
###  Label
###   Map of form widgets to value
config.FORM_BUTTONS = [
    [
        (
            "Unrelated: Scripts", {
                "due_widget": "Unrelated to scripts",
                "file_field_widget": True,
            }
        ),
        (
            "Unrelated: Provenance", {
                "due_widget": "Unrelated to provenance",
                "file_field_widget": True,
            }
        ),
        (
            "Both", {
                "due_widget": "Unrelated to scripts. Unrelated to provenance",
                "file_field_widget": True,
            }
        ),
        (
            "Ok", {
                "work_type_widget": "WorkOk",
                "file_field_widget": True,
            }
        ),
    ],
]

### List of text fields in forms
### Each tuple has 3 fields
###   Label
###   Work attribute
###   Widget variable (use none if you do not want a variable)
config.FORM_TEXT_FIELDS = [
    ("Related", "may_be_related_to", None),
    ("Display", "display", None),
    ("Summary", "summary", None),
    ("Star", "star", None),
    ("Link", "link", None),
]

### Module setting. Do not change it
config.MODULES["places"] = places
config.MODULES["work"] = work
config.MODULES["citations"] = citations
config.MODULES["groups"] = groups

