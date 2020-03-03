import os
import textwrap
from pathlib import Path
from string import ascii_lowercase
from copy import copy

from selenium import webdriver
from IPython.display import HTML
from bibtexparser.customization import homogenize_latex_encoding

from snowballing import config
from snowballing.collection_helpers import define_cvar, setitem, consume
from snowballing.collection_helpers import callable_get, remove_empty
from snowballing.config_helpers import set_config, work_by_varname
from snowballing.config_helpers import last_name_first_author, Site
from snowballing.config_helpers import find_work_by_info, str_item
from snowballing.config_helpers import generate_title
from snowballing.utils import match_any, compare_str
from snowballing.rules import ModifyRules

## Tool version
config.JOHN_SNOW_VERSION = "1.0.0"

## Database path. Do not change it unless you know what you are doing
config.DATABASE_DIR = Path(__file__).parent.resolve()

## Text editior path
config.TEXT_EDITOR = "code"  # VSCode
# config.TEXT_EDITOR = "subl"  # Sublime Text
## Text editor argument for opening in a given line.
## Use a format string with arguments {year_path} and {line}
config.LINE_PARAMS = "--goto {year_path}:{line}"  # VSCode
#config.LINE_PARAMS = "{year_path}:{line}"  # Sublime Text

## Web Driver
config.WEB_DRIVER = lambda: webdriver.Chrome()
#config.WEB_DRIVER = lambda: webdriver.Firefox()

## Run widget
## Use True to indicate that widgets that generate executable code should have a text area with a button for running the code.
## Otherwise, they modify notebook cells (unsafe)
config.RUN_WIDGET = True 

## PDF Extractor. Use string argumen {path} to define the path
config.PDF_EXTRACTOR = None
#config.PDF_EXTRACTOR = "java -jar refExtractor.jar full {path}"



## List of possible work class tuples
## Each tuple has the follwing elements:
##   Class Name
##   Category name
##   Graph visibility (Options: display, hide, always_hide)
##   Graph node color
##   Graph node text color
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
## Default class for insertion
config.DEFAULT_CLASS = "Work"

## Similary Ratio for matching places
config.SIMILARITY_RATIO = 0.8

## Check Deprecation
config.CHECK_DEPRECATION = True


### Fields

## Debug fields during BibTeX export
config.DEBUG_FIELDS = True

## List of exportable work fields to BibTeX
config.WORK_FIELDS = [
    "ENTRYTYPE",
    # Individuals
    "author", "bookauthor", "editor", "editora", "editorb", "editorc", 
    "afterword", "annotator", "commentator", "forward", "introduction",
    "translator", "holder",
    # Orgs
    "institution", "organization", "publisher", "school",
    # Titles
    "title", "indextitle", "booktitle", "maintitle", "journaltitle",
    "issuetitle", "eventtitle", "reprinttitle", "series", 
    # Volumes and versions
    "volume", "number", "part", "chapter", "issue", "volumes", "edition",
    "version", "pubstate",
    # Pages
    "pages", "pagetotal", "bookpagination", "pagination", 
    # Dates
    "date", "eventdate", "urldate", "month", "year",
    # Places
    "address", "location", "venue", "journal",
    # Digital
    "url", "doi", "eid", "eprint", "eprinttype", "howpublished",
    # Types
    "type", "entrysubtype",
    # Misc
    "addendum", "note", "language", "abstract", "annotation", "annote", "file", 
    "library", "key", 
    # International Standards
    "isan", "isbn", "ismn", "isrn", "issn",
    # Labels
    "label", "shorthand", "shorthandintro",
    # Non-printable data
    "execute", "keywords", "options", "ids",
    # Related
    "related", "relatedtype", "relatedstring", 
    # Data
    "entryset", "crossref", "xref", "xdata",
    # Lang
    "langid", "langidopts", "gender",
    # Sorting
    "presort", "sortkey", "sortname", "sortshorthand", "shorttitle",
    "indexsorttitle", "sortyear",
]

## Ignore fields when exporting to BibTeX
##   Regexes that starts with ^ and ends with $
config.BIBTEX_IGNORE_FIELDS = [
    "ID", 

    # Tool
    "_.*",
    "_excerpt", "_div", "_pyref", "_work_type", "_ref",
    "_scholar", "_scholar_id", "_scholar_ok", "_cluster_id",
    "_citation_id", "_prefix", "_link",
    "_tyear", "_draw",

    # Custom
    "_note", "_due", "_url",

    # Approach
    "_display", "_approach_name",
]


### Transformation Rules

## Map BibTex to Info object
config.BIBTEX_TO_INFO = {
    "<before>": [
        ("year", lambda old, new, current: int(
            (old["year"][:4] or 0) if "[in press]" in old.get("year", "")
            else old.get("year", 0)
        )),
    ],
    "<middle>": [
        ("_pyref", lambda old, new: info_to_pyref(old)),
    ],
    "<after>": [
        ("title", lambda old, new, current: new["title"].replace("{", "").replace("}", ""))
    ],
    "year": [
        ("_note", lambda x: "in press" if "[in press]" in x.get("year", "") else None)
    ],
    "<article>": [
        ("_excerpt", lambda article, new: article.attrs["excerpt"][0]),
        ("_cluster_id", lambda article, new: article.attrs["cluster_id"][0]),
        ("_scholar", lambda article, new: article.attrs["url_citations"][0]),
        ("_div", lambda article, new: article.div),
    ],
    "<set_ignore_keys>": {"_excerpt", "_div", "_pyref", "_work_type", "_ref", "_prefix"},
    "<set_ignore_but_show>": {"year"},
    "<set_always_show>": {"title", "author", "ENTRYTYPE", "year"},
    "<set_order>": ["title", "author", "ENTRYTYPE", "year"],
    "<scholar_ok>": "_scholar_ok",
    #"<set_before>": lambda work, info: [],
}   

## Map BibTex to Info object. Set _work_type=Work
config.BIBTEX_TO_INFO_WITH_TYPE = (
    ModifyRules(config.BIBTEX_TO_INFO, "with_type")
    .append("<before>", ("_work_type", "Work"))
).rules



## Map BibTex to Info object. Ignore ID attribute
config.BIBTEX_TO_INFO_IGNORE_SET_ID = (
    ModifyRules(config.BIBTEX_TO_INFO, "ignore_set")
    .add("<set_ignore_keys>", "ID")
).rules


## Convert Article info to Info object
#   If the work exists, it should populate the attribute _nwork (use find_work_by_info)
config.ARTICLE_TO_INFO = {
    "<after>": [
        (None, lambda old, new, current:
            [
                setitem(new, "_pyref", 'Site("{title}", "{url}")'.format(**new)),
                setitem(new, "_nwork", Site(new["title"], new["url"]))
            ] if new.get("_work_type") == "Site" else
            [
                setitem(new, "_nwork", work_by_varname(new["_pyref"])),
                setitem(new, "_title", new["_nwork"].title),
            ] if new.get("_work_type") == "Ref" else 
            [
                setitem(new, "_pyref", info_to_pyref(new)) if "_pyref" not in new else None,
                setitem(new, "_nwork", find_work_by_info(new, set())),
            ]
        )
    ],
    "_div": [None],
    "_citation_id": [None],
    "<article>": [
        (None, lambda article, new: [
            setitem(article, "_ref", article.get("_citation_id", "")),
        ]),
    ]
}



## Map Info object to Insert Code
config.INFO_TO_INSERT = {
    "<before>": [
        ("_work_type", "Work"), ("_due", ""),
        ("author", ""), ("other", ""),
    ],
    "<middle>": [
        ("other", lambda old, new, current: [
            "{}={!r},".format(key, consume(current, key)) # .replace('"', r'\"')
            for key in copy(current)
        ]),
        ("attributes", lambda old, new: "\n            ".join(remove_empty([
            new["_due"], new["author"],
        ] + new["other"]))),
    ],
    "<result>": lambda old, new, current: textwrap.dedent("""
        {_pyref} = DB({_work_type}(
            {year}, "{title}",
            {attributes}
        ))""".format(**new)),
    "_work_type": ["_work_type"],
    "year": ["year"],
    "title": ["title"],
    "author": [("author", str_item("author"))],
    "_pyref": ["_pyref"],
    "_due": [("_due", str_item("_due"))] ,
    "_excerpt": [None],
    "_prefix": [None],
    "_ref": [None],
}


## Modify Info object for finding work
config.FIND_INFO_WORK = {
    "<skip>": [
        ("_work_type", "Site"),
    ],
    "<ignore>": ["_year", "_work", "_key"],
    "<before>": [
        ("_work", lambda old: work_by_varname(old["ID"]) if "ID" in old else None),
        ("_key", lambda old: old["ID"] if "ID" in old else None),
    ],
    "year": ["year", "_year"],
}


## Convert Work object into BibTex dict object
#   The "new" object starts with three parameters
#     _name: override metakey name
#     _homogeneize: bibtex homogeneize
#     _acronym: use acronym instead of full place text
#   The result do not need these attributes
def _work_to_bibtex_middle(work, new, current):
    if config.DEBUG_FIELDS:
        use = callable_get(config.WORK_TO_BIBTEX, "<use>", [])
        ignore = callable_get(config.WORK_TO_BIBTEX, "<ignore>", [])
        for key in dir(work):
            if not match_any(key, use) and not match_any(key, ignore):
                print("[DEBUG WARNING]", work._metakey, work.year, key)

config.WORK_TO_BIBTEX = {
    "<before>": [
        ("ID", lambda work, new, current: (
            new["_name"] if new.get("_name", None) else
            work._metakey if hasattr(work, "_metakey") else
            (lambda split: (split[0] if split else "a") + str(work.year))(work.author.split())
        )),
    ],
    "<middle>": [
        (None, _work_to_bibtex_middle),
    ],
    "<ignore>": lambda: config.BIBTEX_IGNORE_FIELDS,
    "<use>": lambda: config.WORK_FIELDS,
    "<result>": lambda work, new, current: (
        [
            consume(new, "_name"),
            consume(new, "_acronym"),
            homogenize_latex_encoding(new) if consume(new, "_homogeneize") else new,
        ][-1]
    ), 
}


### Snowballing Forms

@set_config("user")
def convert_citation_text_lines_to_info(text):
    """Convert lines of format [N] author name place other year' to Info object
    If it is an invalid format, it should return "Incomplete".
    """
    lines = text.strip().split("\n")
    info = {
        "_citation_id": lines[0].strip(),
    }
    found = False
    other = []

    if lines[-1].strip().startswith(">") and len(lines) >= 2:
        # [N] > varname
        info["_pyref"] = lines[-1][1:].strip()
        info["_work_type"] = "Ref"
        found = True
        other = lines[1:-1]
    elif lines[-1].strip().startswith("http") and len(lines) >= 3:
        # [N] WebName http://...
        info["title"] = lines[1].strip()
        info["url"] = lines[-1].strip()
        info["_work_type"] = "Site"
        found = True
        other = lines[2:-1]
    elif len(lines) >= 5 and lines[-1].strip().isnumeric():
        # [N] author name place other year
        info["author"] = lines[1].strip()
        info["title"] = lines[2].strip()
        split = lines[3].strip().split("=")
        if len(split) > 1:
            info[split[0]] = "=".join(split[1:])
        else:
            info["booktitle"] = lines[3].strip()
        info["year"] = int(lines[-1].strip())
        info["_work_type"] = "Work"
        found = True
        other = lines[4:-1]
    if found:
        for num, line in zip(range(1, 10000), other):
            line = line.strip()
            split = line.split("=")
            if len(split) > 1:
                info[split[0]] = "=".join(split[1:])
            else:
                info["_other{}".format(num)] = line
        return info
    
    return "Incomplete"


@set_config("user")
def info_to_pyref(info):
    """Create pyref for info"""
    if "_prefix" in info:
        display = info["_prefix"]
    else:
        display = last_name_first_author(info["author"])
    pyref = "{display}{year}".format(display=display, year=info["year"])
    for letter in ascii_lowercase:
        if not work_by_varname(pyref + letter):
            break
    pyref += letter
    return pyref


@set_config("user")
def set_info_letter(info, letter):
    """Set letter of info object"""
    if info["_pyref"][-1].isalpha():
        info["_pyref"] = info["pyref"][:-1]
    info["_pyref"] += letter



# Insert form
config.FORM = {
    # List of widgets
    #   Each widget has at least 3 fields
    #     Type (text, dropdown, toggle, button)
    #     Label
    #     Variable
    #   Some widget requ-ire extra fields
    #     text, dropdown, and toggle: 4th field indicates the value
    #     dropdown: 5th field is a list with options
    "widgets": [
        # Base
        [
            "dropdown", "Type", "_work_type", config.DEFAULT_CLASS, 
            [tup[0] for tup in config.CLASSES]
        ],
        ["toggle", "File", "file_field", False],
        ["text", "Due", "_due", ""],
        ["text", "Year", "year", ""],
        ["text", "Prefix Var", "_prefix", ""],
        ["text", "PDFPage", "pdfpage", ""],
        ["text", "Link", "_url", None],
        # Buttons
        ["button", "Ok", "_b1"],
        
    ],
    # List of events
    #   Each event has 3 fields
    #     Widget variable
    #     Listener (observe, click)
    #     Action. It can be:
    #       A dictionary indicating which values to chance
    #       A list with the action (first item is a str) and its parameters (other actions)
    #       A list of actions to run in sequence
    "events": [
        # Base
        ["_due", "observe", [
            ["if",
                ["and",
                    ["!=", ":_due", ""],
                    ["==", ":_work_type", "Work"]
                ],
                {
                    "_work_type": "WorkUnrelated",
                },
                ["if",
                    ["and",
                        ["==", ":_due", ""],
                        ["==", ":_work_type", "WorkUnrelated"]
                    ],
                    {
                        "_work_type": "Work"
                    },
                    []

                ]
            ]

        ]],
        # Buttons
        ["_b1", "click", [
            {
                "_work_type": "WorkOk",
                "file_field": True,
            },
            ["reload"],
        ]],
    ],
    # Exhibition of the widges.
    #   Each list indicates a row with other widgets
    #   I suggest using no more than 4 buttons in a row 
    #   and no more than 2 inputs in a row
    "order": [
        ["_b1"],
        ["_work_type", "file_field"],
        ["_due", "_url"],
        ["year", "_prefix"],
    ],
    # Show operation
    #   Use the same "DSL" as the events to update info object.
    "show": [
        ["update_info", "_due", ":_due", None, ""],
        ["update_info", "_work_type", ":_work_type", None, "Work"],
        ["if", 
            ["or",
                ["update_info", "year", ":year", None, ""],
                ["update_info", "_prefix", ":_prefix", None, ""],
            ],
            ["pyref"],
            []
        ],
        ["update_info", "_file", ":file_field", ["+", "._pyref", r"\.pdf"], False],
        ["update_info", "_file", ":pdfpage", ["+", ".file", "#page=", ":pdfpage"], ""],
        ["update_info", "_url", ":_url", None, ""],
    ]
}


@set_config("user")
def check_insertion(nwork, info, citation_var, citation_file, should_add, ref=''):
    """Check info validity after executing snowballing.create_info_code
    Return dictionary of warning fields

    This version: 
        - checks for existence of pdf in the disk
        - checks for definition of place
        - checks for citation variable
        - checks for work_type
    """
    result = {}
    may_not_have_file = (
        '_url' in info
        or info.get('_work_type', '') in ('nofile', 'site')
        or (nwork is not None and (
            hasattr(nwork, '_url')
            or nwork._category in ('nofile', 'site')
        ))
    ) 
    if not may_not_have_file:
        filepath = getattr(nwork, "_file", info.get('_file', '{}.pdf'.format(info['_pyref'])))
        if not os.path.exists(os.path.join("files", filepath)):
            result["pdf"] = filepath

    if citation_var and not work_by_varname(citation_var):
        result["citation"] = "Work {} not found".format(citation_var)

    if not nwork and info.get("_work_type", "Work") == "Work":
        info["_work_type"] = "Work"
        result["type"] = info["_work_type"]

    return result

@set_config("user")
def check_load(work, varname, warning=lambda x: print(x)):
    """Check conditions on load"""
    if not hasattr(work, "_scholar_id"):
        warning("[Warning] Work {} does not have _scholar_id".format(varname))


### Snowballing display

@set_config("user")
def display_article(article):
    """Display article in widget"""
    if "_div" in article:
        return [
            HTML("""
                <style>
                .gs_or_svg {
                    position: relative;
                    width: 29px;
                    height: 16px;
                    vertical-align: text-bottom;
                    fill: none;
                    stroke: #1a0dab;
                }
                </style>
            """),
            HTML(repr(article["_div"]))
        ]
    else:
        return [
            article["title"]
        ]

### Query Scholar

@set_config("user")
def query_str(work):
    """Return string to query work on scholar"""
    return work.title + " " + work.author

### Work Attributes

@set_config("user")
def work_post_init(work):
    """Instructions to execute after Work __init__

    Default: set display to title if display is None
    """
    pass

@set_config("user")
def work_eq(first, second):
    """Compare work
    
    Default: compare place, title and year
    """
    return (
        first.title == second.title
        and first.year == second.year
    )

@set_config("user")
def work_hash(work):
    """Uniquely identify work

    Default: use title and year
    """
    return hash((work.title, work.year))

@set_config("user")
def info_work_match(info, work):
    """Check if an Info object matches to a Work object
    
    Default: checks for exact matches by cluster_id, scholar_id, (year, name, authors) of aliases
      and similar titles
      It uses matches on places and years to reduce the similarity requirements for matching titles
    """
    if info.get("_cluster_id", "<ii>") == getattr(work, "_cluster_id", "<iw>"):
        return True
    if info.get("_scholar_id", "<ii>") == getattr(work, "_scholar_id", "<iw>"):
        return True
    
    for alias in get_work_aliases(work):
        condition = (
            alias[0] == info["year"]
            and alias[1] == info["title"]
            and (
                len(alias) > 2 and alias[2] == info["author"]
                or getattr(work, "author", None) == info["author"]
            )
        )
        if condition:
            return True

    required = 0.9
    if info["year"] == 0:
        required += 0.1

    # ToDo: compare other fields and reduce required
    
    if compare_str(getattr(work, "title"), info.get("title")) > required:
        return True

    return False

## Get work display
@set_config("user")
def work_display(work):
    """Get work display"""
    return work._metakey


### Aliases

@set_config("user")
def get_work_aliases(work):
    """Get list of aliases from work

    Default: the tool uses the attributes "alias" and "aliases" to represent aliases
    """
    if hasattr(work, "_alias"):
        return [work._alias]
    if hasattr(work, "_aliases"):
        return work._aliases
    return []


@set_config("user")
def get_alias_year(work, alias):
    """Get year from alias

    Default: return first element of tuple/list that represents the alias    
    """
    return alias[0]


### Graph Attributes

## Get place name from work. fn(work) 
@set_config("user")
def graph_place_text(work):
    """Get place text for graph
    
    Default: return place acronym
    """
    for key in ["booktitle", "journal", "school", "howpublished"]:
        value = getattr(work, key, None)
        if value is not None:
            return value

## Generate tooltip for place from work. fn(work)
@set_config("user")
def graph_place_tooltip(work):
    """Generate place tooltip

    Default: tooltip with all information from Place object
    """
    for key in ["booktitle", "journal", "school", "howpublished"]:
        value = getattr(work, key, None)
        if value is not None:
            return key 
    

## Get work link. fn(work)
@set_config("user")
def work_link(work):
    """Create hyperlink based on work attributes. 
    The attribute _link is set by the graph creator and it specifies the priority order of link types
    
    Default: uses attributes file, link, or scholar to create link
    """
    for link_type in work._link:
        if link_type == "file" and work._file:
            return "files/" + work._file
        if link_type == "link" and hasattr(work, "_url") and work._url:
            return work._url
        if link_type == "scholar" and hasattr(work, "_scholar"):
            return work._scholar
    return None


## Generate tooltip for work. fn(work)
@set_config("user")
def work_tooltip(work):
    """Generate work tooltip

    Default: tooltip with paper title and authors
    """
    from snowballing.operations import work_to_bibtex
    return (
        "{}\n{}".format(work.title, work.author)
        + "\n\n" + work_to_bibtex(work)
    )

@set_config("user")
def citation_tooltip(citation):
    """Generate citation tooltip"""
    return (
        "{0} -> {1}".format(citation.work._metakey, citation.citation._metakey)
        + generate_title(citation, ignore={"_.*", "work", "citation"})
    )


### Approaches

config.APPROACH_FORCE_PREFIX = "_force_"
config.APPROACH_RELATED_CATEGORY = "Related"

## Get work ids from approach. fn(approach, works)
@set_config("user")
def approach_ids_from_work(approach, works):
    for work in approach._work:
        if work in works and ("snowball" in work._category or "ok" in work._category):
            yield works[work]["ID"]

## Get approach display. fn(approach)
@set_config("user")
def approach_display(approach):
    return approach._display

### Database

## Module setting. Do not change it
from . import work, citations, groups

#config.MODULES["places"] = places
config.MODULES["work"] = work
config.MODULES["citations"] = citations
config.MODULES["groups"] = groups

## Map of Work attributes used by the tool
import snowballing.models
for name in dir(snowballing.models):
    obj = getattr(snowballing.models, name, None)
    category = getattr(obj, "category", None)
    if category is not None:
        del obj.category
        obj._category = category

config.ATTR = {
    # Work
    "category": "_category",
    "metakey": "_metakey", 
    "pyref": "_pyref", 
    "year": "year", 
    "name": "title",
    "site_link": "_link",
    "email_authors": "author",
    "citation_file": "_citation_file",


    # Approach
    "approach_dont_cite": "_dont_cite",
    "approach_work": "_work",
}


## Similar to ATTR variable, bu provide a direct map from existing keys from scholar
config.SCHOLAR_MAP = {
    "scholar_id": "_scholar_id",
    "cluster_id": "_cluster_id",
    "scholar": "_scholar",
    "scholar_ok": "_scholar_ok",
}


define_cvar(config.ATTR)
