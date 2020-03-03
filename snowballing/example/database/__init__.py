import os
from pathlib import Path

from selenium import webdriver

from snowballing import config
from snowballing.collection_helpers import define_cvar
from snowballing.config_helpers import set_config
from snowballing.operations import work_by_varname
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
    "entrytype", "year", "name", "authors", "place",
    "booktitle", "bookauthors", "edition", "available",
    "volume", "number", "section", "pp", "article",
    "doi", "isbn",  "proceedings", "issn",
    "organization", "publisher", "school", "institution", "track",
    "ref", "local", "editors", "awards",
    "special", "website", "link", "scholar", "shorttitle", "address",
]

## Ignore fields when exporting to BibTeX
##   Regexes that starts with ^ and ends with $
config.BIBTEX_IGNORE_FIELDS = [
    "excerpt", "month", "bookname", "url", "ID", 

    # Tool
    "_.*", "force_.*", "file.*", "category", "alias", "aliases", "scholar_ok",
    "scholar", "cluster_id", "scholar_id", "display", "metakey", "due", "_tyear",
    "citation_file", "notes", "tracking", "snowball", "request", "_draw",
    "may_be_related_to", "note",

    # Extra
    "summary", "star", "approach_name",
]


### Transformation Rules

## Map BibTex to Info object
#config.BIBTEX_TO_INFO = (
#    ModifyRules(config.BIBTEX_TO_INFO, "user")
#).rules

## Map BibTex to Info object. Set _work_type=Work
#config.BIBTEX_TO_INFO_WITH_TYPE = (
#    ModifyRules(config.BIBTEX_TO_INFO_WITH_TYPE, "user")
#).rules


## Map BibTex to Info object. Ignore ID attribute
#config.BIBTEX_TO_INFO_IGNORE_SET_ID = (
#    ModifyRules(config.BIBTEX_TO_INFO_IGNORE_SET_ID, "user")
#).rules


## Convert Article info to Info object
#config.ARTICLE_TO_INFO = (
#    ModifyRules(config.ARTICLE_TO_INFO, "user")
#).rules


## Map Info object to Insert Code
#config.INFO_TO_INSERT = (
#    ModifyRules(config.INFO_TO_INSERT, "user")
#).rules


## Modify Info object for finding work
#config.FIND_INFO_WORK = (
#    ModifyRules(config.FIND_INFO_WORK, "user")
#).rules


## Convert Work object into BibTex dict object
#config.WORK_TO_BIBTEX = (
#    ModifyRules(config.WORK_TO_BIBTEX, "user")
#).rules


### Snowballing Forms

## Convert lines of format [N] author name place other year' to Info object. fn(text)
#set_config("user")(config.convert_citation_text_lines_to_info)


## Create pyref from Info. fn(info)
#set_config("user")(config.info_to_pyref)


## Set letter of info object. fn(info, letter)
#set_config("user")(config.set_info_letter)



# Insert form
config.FORM = (
    ModifyRules(config.FORM, "user")
    .append_all("widgets", [
        ["text", "Star", "star", None],
        ["text", "Summary", "summary", None],
        ["button", "Unrelated: Scripts", "_b2"],
        ["button", "Unrelated: Provenance", "_b3"],
        ["button", "Both", "_b4"],

    ])
    .append_all("events", [
        ["_b2", "click", [
            {
                "due": "Unrelated to scripts",
                "file_field": True,
            },
            ["reload"]
        ]],
        ["_b3", "click", [ 
            {
                "due": "Unrelated to provenance",
                "file_field": True,
            },
            ["reload"]
        ]],
        ["_b4", "click", [
            {
                "due": "Unrelated to scripts. Unrelated to provenance",
                "file_field": True,
            },
            ["reload"],
        ]],
    ])
    .replace("order", [
        ["_b2", "_b3", "_b4", "_b1"],
        ["work_type", "file_field"],
        ["due", "place"],
        ["year", "prefix"],
        ["pdfpage", "may_be_related_to"],
        ["display", "summary"],
        ["star", "link"],
    ])
    .append_all("show", [
        ["update_info", "summary", ":summary", None, ""],
        ["update_info", "star", ":star", None, ""],
    ])
).rules


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
        'link' in info
        or info.get('_work_type', '') in ('nofile', 'site')
        or info.get('place', '') == 'Patent'
        or (nwork is not None and (
            hasattr(nwork, 'link')
            or nwork.category in ('nofile', 'site')
            or getattr(getattr(nwork, 'place', None), 'name', '') == "Patent"
        ))
    ) 
    if not may_not_have_file:
        filepath = getattr(nwork, "file", info.get('file', '{}.pdf'.format(info['pyref'])))
        if not os.path.exists(os.path.join("files", filepath)):
            result["pdf"] = filepath

    if info.get("_work_type") not in ("Site", "Ref"):
        if 'place' not in info:
            result["place1"] = info['place1']

    if citation_var and not work_by_varname(citation_var):
        result["citation"] = "Work {} not found".format(citation_var)

    if not nwork and info.get("_work_type", "Work") == "Work":
        info["_work_type"] = "Work"
        result["type"] = info["_work_type"]

    return result

## Check conditions on load
#set_config("user")(config.check_load)


### Snowballing display

## Display article in widget. fn(article)
#set_config("user")(config.display_article)

### Query Scholar

## Return string to query work on scholar. fn(work)
#set_config("user")(config.query_str)

### Work Attributes

## Instructions to execute after Work __init__. fn(work)
#set_config("user")(config.work_post_init)

## Compare Work. fn(first, second)
#set_config("user")(config.work_eq)

## Uniquely identify Work. fn(work)
#set_config("user")(config.work_hash)

## Check if an Info object matches to a Work object. fn(info, work)
#set_config("user")(config.info_work_match)

## Get work display. fn(work)
#set_config("user")(config.work_display)

### Aliases

## Get list of aliases from work. fn(work)
#set_config("user")(config.get_work_aliases)

## Get year from alias. fn(work, alias)
#set_config("user")(config.get_alias_year)


### Graph Attributes

## Get place name from work. fn(work) 
#set_config("user")(config.graph_place_text)

## Generate tooltip for place from work. fn(work)
#set_config("user")(config.graph_place_tooltip)

## Get work link. fn(work)
#set_config("user")(config.work_link)

## Generate tooltip for work. fn(work)
#set_config("user")(config.work_tooltip)

## Generate tooltip for citation. fn(citation)
#set_config("user")(config.citation_tooltip)


### Approaches

config.APPROACH_FORCE_PREFIX = "force_"
config.APPROACH_RELATED_CATEGORY = "Related"

## Get work ids from approach. fn(approach, works)
#set_config("user")(config.approach_ids_from_work)

## Get approach display. fn(approach)
#set_config("user")(config.approach_display)


### Database

## Module setting. Do not change it
from . import places, work, citations, groups

config.MODULES["places"] = places
config.MODULES["work"] = work
config.MODULES["citations"] = citations
config.MODULES["groups"] = groups

## Map of Work attributes used by the tool
#config.ATTR = ... 

## Similar to ATTR variable, bu provide a direct map from existing keys from scholar
#config.SCHOLAR_MAP = ...

define_cvar(config.ATTR)
