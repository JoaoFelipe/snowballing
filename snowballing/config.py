"""This module configures the snowballing.

Please, use the database __init__ to replace these configurations.
"""
import textwrap
from copy import copy
from pathlib import Path

from string import ascii_lowercase
from bibtexparser.customization import homogenize_latex_encoding
from IPython.display import HTML

from .collection_helpers import callable_get, define_cvar
from .collection_helpers import consume, setitem, remove_empty
from .config_helpers import reorder_place, last_name_first_author
from .config_helpers import var_item, str_list, str_item, sequence
from .config_helpers import work_by_varname, find_work_by_info, Site
from .rules import ModifyRules
from .utils import compare_str, match_any

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

# Check Deprecation
CHECK_DEPRECATION = True


### Fields

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


### Transformation Rules

def _place_value(place1):
    """Get place value based on similarity

    It considers a match if the matching ratio for the place name
    is >= config.SIMILARITY_RATIO (0.8).

    It also considers a match if the acronym matches.

    Doctest:

    .. doctest::

        >>> info = {"place1": "IPAW"}
        >>> _place_value("IPAW")
        'IPAW'
        >>> _place_value("Software Engineering, International Conference on")
        'ICSE'
        >>> _place_value("A random conference") is None
        True
    """
    from .operations import load_places_vars
    place = reorder_place(place1)

    maxmatch = max(
        (max(
            compare_str(place, varvalue.name),
            1 if place == varvalue.acronym else 0
        ), varname, varvalue) for varname, varvalue in load_places_vars()
    )

    if maxmatch[0] >= SIMILARITY_RATIO or maxmatch[2].name in place:
        return maxmatch[1]
    

# Map BibTex to Info object
BIBTEX_TO_INFO = {
    "<before>": [
        ("place1", ""),
        ("year", lambda x: int(
            (x["year"][:4] or 0) if "[in press]" in x.get("year", "")
            else x.get("year", 0)
        )),
    ],
    "<middle>": [
        ("place", lambda old, new: _place_value(new["place1"])),
        ("display", lambda old, new: last_name_first_author(new["authors"])),
        ("pyref", lambda old, new: info_to_pyref(new)),
    ],
    "<after>": [
        ("name", lambda old, new, current: new["name"].replace('{', '').replace('}', ''))
    ],
    "title": ["name"],
    "author": ["authors"],
    "address": ["local"],
    "publisher": ["organization"],
    "pages": ["pp"],
    "ENTRYTYPE": ["entrytype"],
    "journal": ["place1"],
    "booktitle": ["place1"],
    "year": [
        ("note", lambda x: "in press" if "[in press]" in x.get("year", "") else None)
    ],
    "<article>": [
        ("excerpt", lambda article, new: article.attrs["excerpt"][0]),
        ("cluster_id", lambda article, new: article.attrs["cluster_id"][0]),
        ("scholar", lambda article, new: article.attrs["url_citations"][0]),
        ("div", lambda article, new: article.div),
    ],
    "<set_ignore_keys>": {"excerpt", "div", "pyref", "display", "place", "_work_type", "_ref"},
    "<set_ignore_but_show>": {"place1", "year"},
    "<set_always_show>": {"name", "authors", "entrytype", "place1", "year"},
    "<set_order>": ["name", "authors", "entrytype", "place1", "year"],
    "<scholar_ok>": "scholar_ok",
    "<set_before>": lambda work, info: [
        setattr(work, "entrytype", work.place.type)
            if not hasattr(work, "entrytype")
            and hasattr(work, "place") else 
            None,
        setattr(info, "place1", info["place"])
            if "place" in info
            and not "place1" in info else
            None,
        setattr(work, "place1", "{} ({})".format(work.place.name, work.place.acronym)),
    ],
}


# Map BibTex to Info object. Set _work_type=Work
BIBTEX_TO_INFO_WITH_TYPE = (
    ModifyRules(BIBTEX_TO_INFO)
    .append("<before>", ("_work_type", "Work"))
).rules


# Map BibTex to Info object. Ignore ID attribute
BIBTEX_TO_INFO_IGNORE_SET_ID = (
    ModifyRules(BIBTEX_TO_INFO, "ignore_set")
    .add("<set_ignore_keys>", "ID")
).rules


# Convert Article info to Info object
#   If the work exists, it should populate the attribute _nwork (use find_work_by_info)
ARTICLE_TO_INFO = {
    "<after>": [
        (None, lambda old, new, current:
            [
                setitem(new, "pyref", 'Site("{name}", "{url}")'.format(**new)),
                setitem(new, "_nwork", Site(new["name"], new["url"]))
            ] if new.get("_work_type") == "Site" else
            [
                setitem(new, "_nwork", work_by_varname(new["pyref"])),
                setitem(new, "name", new["_nwork"].name),
                setitem(new, "place", new["_nwork"].place.name),
            ] if new.get("_work_type") == "Ref" else 
            [
                setitem(new, "place", _place_value(new["place1"])) if "place" not in new else None,
                setitem(new, "display", last_name_first_author(new["authors"])) if "display" not in new else None,
                setitem(new, "pyref", info_to_pyref(new)) if "pyref" not in new else None,
                setitem(new, "_nwork", find_work_by_info(new, set())),
            ]
        
        )
    ],
    "div": [None],
    "citation_id": [None],
    "<article>": [
        (None, lambda article, new: 
            [
                setitem(article, "_show_site", True),
                setitem(article, "_ref", article.get("citation_id", "")),
            ] if new.get("_work_type") == "Site" else
            [
                setitem(article, "name", new.get("name")),
                setitem(article, "place", new.get("place")),
                setitem(article, "_ref", article.get("citation_id", "")),
            ] if new.get("_work_type") == "Ref" else [
                setitem(article, "_ref", article.get("citation_id", "")),
            ]
           
        ),
    ]
}


# Map Info object to Insert Code
INFO_TO_INSERT = {
    "<before>": [
        ("work_type", "Work"), ("due", ""), ("related", ""),
        ("display", ""), ("authors", ""), ("the_place", ""), ("other", ""),
    ],
    "<middle>": [
        ("the_place", sequence([
            var_item("place", obj="new"),
            str_item("place1", obj="new"), 
        ])),
        ("other", lambda old, new, current: [
            '{}={!r},'.format(key, consume(current, key)) # .replace('"', r'\"')
            for key in copy(current)
        ]),
        ("attributes", lambda old, new: "\n            ".join(remove_empty([
            new["due"], new["related"], new["display"],
            new["authors"], new["the_place"]
        ] + new["other"]))),
    ],
    "<result>": lambda old, new, current: textwrap.dedent("""
        {pyref} = DB({work_type}(
            {year}, "{name}",
            {attributes}
        ))""".format(**new)),
    "_work_type": ["work_type"],
    "year": ["year"],
    "name": ["name"],
    "authors": [("authors", str_item("authors"))],
    "display": [("display", str_item("display"))],
    "pyref": ["pyref"],
    "place": ["place"],
    "place1": ["place1"],
    "may_be_related_to": [("related", str_list("may_be_related_to"))],
    "due": [("due", str_item("due"))] ,
    "excerpt": [None],
    "_ref": [None],
}


# Modify Info object for finding work
#   <skip> and <ignore> only exist for this
FIND_INFO_WORK = {
    "<skip>": [
        ("_work_type", "Site"),
    ],
    "<ignore>": ["_year", "_work", "_key"],
    "<before>": [
        ("place", lambda old: 
            None if "entrytype" not in old else
            "Thesis" if old["entrytype"] in ("phdthesis", "mastersthesis") else
            "TechReport" if old["entrytype"] == "techreport" else
            "Book" if old["entrytype"] == "book" else
            None
        ), 
        ("_work", lambda old: work_by_varname(old['ID']) if 'ID' in old else None),
        ("_key", lambda old: old['ID'] if 'ID' in old else None),
    ],
    "year": ["year", "_year"],
    "school": ["local"],
}


# Convert Work into BibTex dict
#   The "new" object starts with three parameters
#     _name: override metakey name
#     _homogeneize: bibtex homogeneize
#     _acronym: use acronym instead of full place text
#   The result do not need these attributes
def _work_to_bibtex_middle(work, new, current):
    if DEBUG_FIELDS:
        use = callable_get(WORK_TO_BIBTEX, "<use>", [])
        ignore = callable_get(WORK_TO_BIBTEX, "<ignore>", [])
        for key in dir(work):
            if not match_any(key, use) and not match_any(key, ignore):
                print("[DEBUG WARNING]", work.display, work.year, key)
    new_place_key = {
        "incollection": "booktitle",
        "inproceedings": "booktitle",
        "misc": "booktitle",
        "article": "journal",
        "book": None,
        "mastersthesis": None,
        "phdthesis": None,
        "techreport": None,
        "": None
    }[new.get("ENTRYTYPE", "")]
    if hasattr(work, "place"):
        conference_has_acronym = (
            new["_acronym"]
            and work.place.type == "Conference"
            and not work.place.acronym.startswith("<")
        )
        if conference_has_acronym:
            new[new_place_key] = str(work.place.acronym)
        else:
            new[new_place_key] = str(work.place)
    elif hasattr(work, "place1"):
        new[new_place_key] = str(work.place1)

WORK_TO_BIBTEX = {
    "<before>": [
        ("ID", lambda work, new, current: (
            new["_name"] if new.get("_name", None) else
            work.metakey if hasattr(work, "metakey") else
            (lambda split: (split[0] if split else "a") + str(work.year))(work.authors.split())
        )),
    ],
    "<middle>": [
        (None, _work_to_bibtex_middle),
    ],
    "<ignore>": lambda: BIBTEX_IGNORE_FIELDS + ["place", "place1"],
    "<use>": lambda: WORK_FIELDS,
    "<result>": lambda work, new, current: (
        [
            consume(new, "_name"),
            consume(new, "_acronym"),
            homogenize_latex_encoding(new) if consume(new, "_homogeneize") else new,
        ][-1]
    ), 
    "name": ["title"],
    "authors": ["author"],
    "local": ["address"],
    "organization": ["publisher"],
    "pp": ["pages"],
    "entrytype": ["ENTRYTYPE"],
}


### Snowballing Forms

def convert_citation_text_lines_to_info(text):
    """Convert lines of format [N] author name place other year' to Info object
    If it is an invalid format, it should return "Incomplete".

    Default: Recognizes 3 patterns:
      - Citation: [N] > varname
      - Site: [N] SiteName http://
      - Work: [N] author name place other year
        - 'other' can be either lines with values, or use the format key=value

    """
    lines = text.strip().split("\n")
    info = {
        "citation_id": lines[0].strip(),
    }
    found = False
    other = []

    if lines[-1].strip().startswith(">") and len(lines) >= 2:
        # [N] > varname
        info["pyref"] = lines[-1][1:].strip()
        info["_work_type"] = "Ref"
        found = True
        other = lines[1:-1]
    elif lines[-1].strip().startswith('http') and len(lines) >= 3:
        # [N] WebName http://...
        info["name"] = lines[1].strip()
        info["url"] = lines[-1].strip()
        info["_work_type"] = "Site"
        found = True
        other = lines[2:-1]
    elif len(lines) >= 5 and lines[-1].strip().isnumeric():
        # [N] author name place other year
        info["authors"] = lines[1].strip()
        info["name"] = lines[2].strip()
        info["place1"] = lines[3].strip()
        info["year"] = int(lines[-1].strip())
        info["_work_type"] = "Work"
        found = True
        other = lines[4:-1]

    if found:
        for num, line in zip(range(1, 10000), other):
            line = line.strip()
            split = line.split('=')
            if len(split) > 1:
                info[split[0]] = '='.join(split[1:])
            else:
                info["other{}".format(num)] = line
        return info
    
    return "Incomplete"


def info_to_pyref(info):
    """Create pyref for info
    
    Doctest:

    .. doctest::
        >>> info_to_pyref({'display': 'pimentel', 'year': 2017})
        'pimentel2017a'
        >>> info_to_pyref({'display': 'pimentel', 'year': 2015})
        'pimentel2015b'
    """
    pyref = "{display}{year}".format(**info)
    for letter in ascii_lowercase:
        if not work_by_varname(pyref + letter):
            break
    pyref += letter
    return pyref


# Insert form
FORM = {
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
            "dropdown", "Type", "work_type", DEFAULT_CLASS, 
            [tup[0] for tup in CLASSES]
        ],
        ["toggle", "File", "file_field", False],
        ["text", "Due", "due", ""],
        ["text", "Place", "place", ""],
        ["text", "Year", "year", ""],
        ["text", "Prefix Var", "prefix", ""],
        ["text", "PDFPage", "pdfpage", ""],
        ["text", "Related", "may_be_related_to", None],
        ["text", "Display", "display", None],
        ["text", "Link", "link", None],
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
        ["due", "observe", [
            ["if",
                ["and",
                    ["!=", ":due", ""],
                    ["==", ":work_type", "Work"]
                ],
                {
                    "work_type": "WorkUnrelated",
                },
                ["if",
                    ["and",
                        ["==", ":due", ""],
                        ["==", ":work_type", "WorkUnrelated"]
                    ],
                    {
                        "work_type": "Work"
                    },
                    []

                ]
            ]

        ]],
        ["place", "observe", [
            ["if",
                ["and",
                    ["==", ":place", "Lang"],
                    ["==", ":work_type", "Work"]
                ],
                {
                    "work_type": "WorkLang"
                },
                []
            ]
        ]],
        # Buttons
        ["_b1", "click", [
            {
                "work_type": "WorkOk",
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
        ["work_type", "file_field"],
        ["due", "place"],
        ["year", "prefix"],
        ["may_be_related_to", "display"],
        ["summary", "link"],
    ],
    # Show operation
    #   Use the same "DSL" as the events to update info object.
    "show": [
        ["if", ["==", ".place", "Lang"],
            {":work_type": "WorkLang"},
            []
        ],
        ["update_info", "due", ":due", None, ""],
        ["update_info", "place", ":place", None, ""],
        ["update_info", "_work_type", ":work_type", None, "Work"],
        ["if", 
            ["or",
                ["update_info", "year", ":year", None, ""],
                ["update_info", "display", ":prefix", None, ""],
            ],
            ["pyref"],
            []
        ],
        ["update_info", "file", ":file_field", ["+", ".pyref", r"\.pdf"], False],
        ["update_info", "file", ":pdfpage", ["+", ".file", "#page=", ":pdfpage"], ""],
        ["update_info", "may_be_related_to", ":may_be_related_to", None, ""],
        ["update_info", "display", ":display", None, ""],
        ["update_info", "link", ":link", None, ""],
    ]
}


### Checks

def check_insertion(nwork, info, citation_var, citation_file, should_add, ref=''):
    """Check info validity after executing snowballing.create_info_code
    Return dictionary of warning fields

    Default: returns place1 if place is not defined and always returns the pdf name 
    """
    result = {}
    result["pdf"] = '{}.pdf'.format(info['pyref'])
    if 'place' not in info and info.get("_work_type") not in ("Site", "Ref"):
        result["place1"] = info['place1']
    return result


def check_load(work, varname, warning=lambda x: print(x)):
    """Check conditions on load"""
    if not hasattr(work, "scholar_id"):
        warning("[Warning] Work {} does not have scholar_id".format(varname))
    if getattr(work, "place", None) is None:
        warning("[Error] Work {} does not have place".format(varname))


### Snowballing display

def display_article(article):
    """Display article in widget"""
    if 'div' in article:
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
            HTML(repr(article["div"]))
        ]
    else:
        return [
            article["name"]
        ]


### Query Scholar

def query_str(work):
    """Return string to query work on scholar"""
    return work.name + " " + work.authors


### Work Attributes

def work_post_init(work):
    """Instructions to execute after Work __init__

    Default: set display to title if display is None
    """
    if getattr(work, "display", None) is None:
        work.display = work.name


def work_eq(first, second):
    """Compare work
    
    Default: compare place, title and year
    """
    if getattr(first, "place", None) != getattr(second, "place", None):
        return False
    return (
        first.name == second.name
        and first.year == second.year
    )


def work_hash(work):
    """Uniquely identify work

    Default: use title and year
    """
    return hash((work.name, work.year))


def info_work_match(info, work):
    """Check if an Info object matches to a Work object
    
    Default: checks for exact matches by cluster_id, scholar_id, (year, name, authors) of aliases
      and similar titles
      It uses matches on places and years to reduce the similarity requirements for matching titles
    """
    if info.get("cluster_id", "<ii>") == getattr(work, "cluster_id", "<iw>"):
        return True
    if info.get("scholar_id", "<ii>") == getattr(work, "scholar_id", "<iw>"):
        return True
    
    for alias in get_work_aliases(work):
        condition = (
            alias[0] == info["year"]
            and alias[1] == info["name"]
            and (
                len(alias) > 2 and alias[2] == info["authors"]
                or getattr(work, "authors", None) == info["authors"]
            )
        )
        if condition:
            return True

    required = 0.9
    if info["year"] == 0:
        required += 0.1

    same_place = (
        "place" in info
        and hasattr(work, "place")
        and getattr(
            getattr(MODULES["places"], info["place"], None),
            "name", "<ii>"
        ) == getattr(
            getattr(work, "place", None),
            "name", "<iw>"
        )
    )
    if same_place:
        required -= 0.1
    
    if compare_str(getattr(work, "name"), info.get("name")) > required:
        return True

    return False


### Aliases

def get_work_aliases(work):
    """Get list of aliases from work

    Default: the tool uses the attributes "alias" and "aliases" to represent aliases
    """
    if hasattr(work, "alias"):
        return [work.alias]
    if hasattr(work, "aliases"):
        return work.aliases
    return []


def get_alias_year(work, alias):
    """Get year from alias\

    Default: return first element of tuple/list that represents the alias    
    """
    return alias[0]


### Graph Attributes

def graph_place_text(work):
    """Get place text for graph
    
    Default: return place acronym
    """
    if getattr(work, "place", None) is not None:
        return work.place.acronym


def graph_place_tooltip(work):
    """Generate place tooltip

    Default: tooltip with all information from Place object
    """
    return work.place.generate_title(orepend="")


def work_link(work):
    """Create hyperlink based on work attributes. 
    The attribute _link is set by the graph creator and it specifies the priority order of link types
    
    Default: uses attributes file, link, or scholar to create link
    """
    for link_type in work._link:
        if link_type == "file" and work.file:
            return "files/" + work.file
        if link_type == "link" and hasattr(work, "link") and work.link:
            return work.link
        if link_type == "scholar" and hasattr(work, "scholar"):
            return work.scholar
    return None


def work_tooltip(work):
    """Generate work tooltip

    Default: tooltip with paper title and authors
    """
    return "{}\n{}".format(work.name, work.authors)


### Approaches

APPROACH_FORCE_PREFIX = "force_"
APPROACH_RELATED_CATEGORY = "Related"

def approach_ids_from_work(approach, works):
    for work in approach.work:
        if work in works and ("snowball" in work.category or "ok" in work.category):
            yield works[work]['ID']


### Database

# Module setting
MODULES = {
    'places': None,
    'work': None,
    'citations': None,
    'groups': None,
}

# Map of Work attributes used by the tool
#   I advise against changing this variable since I may have forgotten to replace an attribute in a function
ATTR = {
    # Work
    "category": "category",
    "metakey": "metakey", 
    "pyref": "pyref", 
    "display": "display", 
    "year": "year", 
    "name": "name",
    "site_link": "link",
    "email_authors": "authors",
    "citation_file": "citation_file",


    # Approach
    "approach_dont_cite": "dont_cite",
    "approach_work": "work",
}


# Similar to ATTR variable, bu provide a direct map from existing keys from scholar
SCHOLAR_MAP = {
    "scholar_id": "scholar_id",
    "cluster_id": "cluster_id",
    "scholar": "scholar",
    "scholar_ok": "scholar_ok",
}

define_cvar(ATTR)
