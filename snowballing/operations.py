"""This module contains functions to :meth:`~reload` the database, load work and
citations from there, and operate BibTeX"""

import importlib
import re
import textwrap
import warnings
import subprocess

from copy import copy
from collections import OrderedDict

from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase


from .collection_helpers import oget, oset, dget, dset, dhas
from .collection_helpers import consume, setitem, callable_get
from .models import DB, Year
from .dbindex import parse_varname, year_file

from .utils import import_submodules
from .utils import parse_bibtex
from .rules import ConvertDict, ConvertWork, old_form_to_new

from . import config

WORK_CACHE = {}
CITATION_CACHE = {}
GROUP_CACHE = {}


def load_work():
    """Load a list of all work in the database"""
    return list(DB.work())


def load_citations():
    """Load a list of all citations"""
    return list(DB.citations())


def load_places_vars():
    """Load all places from the database

    It generates tuples with variable name and Place object

    Doctest:

    .. doctest::

        >>> 'arXiv' in [varname for varname, _ in load_places_vars()]
        True
    """
    places = config.MODULES["places"]
    for varname, varvalue in places.__dict__.items():
        if isinstance(varvalue, places.Place):
            yield varname, varvalue


def load_work_map(year):
    """Load all work from a given year file
    It generates tuples with variable name and Work object

    Doctest:

    .. doctest::

        >>> reload()
        >>> sorted([(work.year, key) for key, work in load_work_map(2015)])
        [(2014, 'murta2014a'), (2015, 'pimentel2015a')]

    (2014, 'murta2014a') appears because it has an alias in 2015
    """
    module = "y{}.py".format(year) if isinstance(year, int) else year
    if module not in WORK_CACHE:
        module = "y9999.py"
    worklist = WORK_CACHE[module]
    for key, work in worklist.__dict__.items():
        if isinstance(work, worklist.Work):
            oset(work, "metakey", key)
            yield key, work


def work_by_varname(varname, year=None):
    """Load work by varname

    Doctest:

    .. doctest::

        >>> reload()
        >>> work = work_by_varname('murta2014a')
        >>> work.year
        2014
    """
    if year is None:
        year = int(parse_varname(varname, 2) or -1)
    module = "y{}.py".format(year) if isinstance(year, int) else year
    if module not in WORK_CACHE:
        return
    worklist = WORK_CACHE[module]
    return getattr(worklist, varname, None)


def load_work_map_all_years():
    """Load all work from all years

    Doctest:

    .. doctest::

        >>> reload()
        >>> sorted([(work.year, key) for key, work in load_work_map_all_years()])
        [(2008, 'freire2008a'), (2014, 'murta2014a'), (2014, 'murta2014a'), (2015, 'pimentel2015a')]

    (2014, 'murta2014a') appears twice because it has an alias in 2015
    """
    years = reversed(sorted(WORK_CACHE.keys()))
    for year in years:
        yield from load_work_map(year)


def _clear_db():
    """Erase database"""
    from .approaches import APPROACHES
    APPROACHES.clear()
    importlib.invalidate_caches()
    DB.clear_places()
    DB.clear_work()
    DB.clear_citations()


def _reload_work():
    """Reload work and create WORD_CACHE"""
    for key, module in import_submodules(config.MODULES["work"]).items():
        yname = key.split(".")[-1]
        fname = (yname + ".py")
        WORK_CACHE[fname] = module
        if not yname.startswith("y") or not yname[1:].isdigit():
            warnings.warn(
                "Invalid name for file {}. Year discovery may fail".format(key)
            )


def reload():
    """Reload all the database

    Doctest:

    ..doctest::

        >>> reload()
        >>> from snowballing.example.database.work.y2014 import murta2014a
        >>> murta2014a.metakey
        'murta2014a'
        >>> from snowballing.example.database.work.y2015 import murta2014a as alias
        >>> alias is murta2014a
        True
    """
    
    _clear_db()
    importlib.reload(config.MODULES["places"])
    _reload_work()
    import_submodules(config.MODULES["citations"])
    import_submodules(config.MODULES["groups"])
    if getattr(config, "CHECK_DEPRECATION", True):
        check_config_deprecation()

    for key, work in load_work_map_all_years():
        oset(work, "metakey", key)
        for alias in config.get_work_aliases(work):
            year = config.get_alias_year(work, alias)
            module = "y{}.py".format(year) if isinstance(year, int) else year
            if module not in WORK_CACHE:
                module = "y9999.py"
            setattr(WORK_CACHE[module], key, work)


def bibtex_to_info(citation, rules=None):
    """Convert BibTeX dict from bibtexparse to info dict for adding a db entry
    
    Doctest:

    .. doctest::

        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J'})
        {'place1': '', 'year': 0, 'name': 'a', 'authors': 'Pim, J', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'year': '2017'})
        {'place1': '', 'year': 2017, 'name': 'a', 'authors': 'Pim, J', 'display': 'pim', 'pyref': 'pim2017a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'year': '2017 [in press]'})
        {'place1': '', 'year': 2017, 'name': 'a', 'authors': 'Pim, J', 'note': 'in press', 'display': 'pim', 'pyref': 'pim2017a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'pages': '1--5'})
        {'place1': '', 'year': 0, 'name': 'a', 'authors': 'Pim, J', 'pp': '1--5', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'journal': 'CiSE'})
        {'place1': 'CiSE', 'year': 0, 'name': 'a', 'authors': 'Pim, J', 'place': 'CiSE', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'ENTRYTYPE': 'article'})
        {'place1': '', 'year': 0, 'name': 'a', 'authors': 'Pim, J', 'entrytype': 'article', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'other': 'a'})
        {'place1': '', 'year': 0, 'name': 'a', 'authors': 'Pim, J', 'display': 'pim', 'pyref': 'pim0a', 'other': 'a'}
   
    """
    rules = rules or config.BIBTEX_TO_INFO
    return ConvertDict(rules).run(citation)


def extract_info(article, rules=None):
    """Extract info from google scholar article

    Doctest:

    .. doctest::

        Mock:

        >>> class Article: pass
        >>> article = Article()
        >>> article.as_citation = lambda: '''
        ... @inproceedings{murta2014noworkflow,
        ...   title={noWorkflow: capturing and analyzing provenance of scripts},
        ...   author={Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana},
        ...   booktitle={International Provenance and Annotation Workshop},
        ...   pages={71--83},
        ...   year={2014},
        ...   organization={Springer}
        ... }'''
        >>> article.attrs = {
        ...   'excerpt': ['Abstract'],
        ...   'cluster_id': ['5458343950729529273'],
        ...   'url_citations': ['http://scholar.google.com/scholar?cites=5458343950729529273&as_sdt=2005&sciodt=0,5&hl=en'],
        ... }
        >>> article.div = None

        Test:

        >>> reload()  # Deterministic name
        >>> extract_info(article)
        {'place1': 'International Provenance and Annotation Workshop', 'year': 2014, 'pp': '71--83', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing and analyzing provenance of scripts', 'entrytype': 'inproceedings', 'place': 'IPAW', 'display': 'murta', 'pyref': 'murta2014b', 'organization': 'Springer', 'ID': 'murta2014noworkflow', 'excerpt': 'Abstract', 'cluster_id': '5458343950729529273', 'scholar': 'http://scholar.google.com/scholar?cites=5458343950729529273&as_sdt=2005&sciodt=0,5&hl=en'}
    """
    rules = rules or config.BIBTEX_TO_INFO
    as_citation = article.as_citation()
    if not isinstance(as_citation, str):
        as_citation = as_citation.decode("utf-8")
    citation = parse_bibtex(as_citation)[0]
    converter = ConvertDict(rules)
    return converter.run(citation, article=article)


def info_to_code(article, rules=None):
    """Convert info dict into code

    Required attributes:

    * pyref
    * display
    * year
    * name
    * place || place1

    Doctest:

    .. doctest::

        >>> print(info_to_code({
        ...   'pyref': 'pimentel2017a',
        ...   'display': 'disp',
        ...   'year': 2017,
        ...   'name': 'snowballing',
        ...   'authors': 'Pimentel, Joao',
        ...   'place1': 'CACM'
        ... }))
        <BLANKLINE>
        pimentel2017a = DB(Work(
            2017, "snowballing",
            display="disp",
            authors="Pimentel, Joao",
            place1="CACM",
        ))

        With place:

        >>> print(info_to_code({
        ...   'pyref': 'murta2014a',
        ...   'display': 'noworkflow',
        ...   'year': 2014,
        ...   'name': 'noWorkflow: capturing and analyzing provenance of scripts',
        ...   'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana',
        ...   'place': config.MODULES['places'].IPAW,
        ... }))
        <BLANKLINE>
        murta2014a = DB(Work(
            2014, "noWorkflow: capturing and analyzing provenance of scripts",
            display="noworkflow",
            authors="Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana",
            place=IPAW,
        ))

        With string place:

        >>> print(info_to_code({
        ...   'pyref': 'murta2014a',
        ...   'display': 'noworkflow',
        ...   'year': 2014,
        ...   'name': 'noWorkflow: capturing and analyzing provenance of scripts',
        ...   'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana',
        ...   'place': 'IPAW',
        ... }))
        <BLANKLINE>
        murta2014a = DB(Work(
            2014, "noWorkflow: capturing and analyzing provenance of scripts",
            display="noworkflow",
            authors="Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana",
            place=IPAW,
        ))

        With _work_type, due, excerpt, others:

        >>> print(info_to_code({
        ...   '_work_type': 'WorkSnowball',
        ...   'due': 'Unrelated to my snowballing',
        ...   'excerpt': 'Ignore excerpt',
        ...   'other': 'Do not ignore other fields',
        ...   'pyref': 'murta2014a',
        ...   'display': 'noworkflow',
        ...   'year': 2014,
        ...   'name': 'noWorkflow: capturing and analyzing provenance of scripts',
        ...   'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana',
        ...   'place': config.MODULES['places'].IPAW,
        ... }))
        <BLANKLINE>
        murta2014a = DB(WorkSnowball(
            2014, "noWorkflow: capturing and analyzing provenance of scripts",
            due="Unrelated to my snowballing",
            display="noworkflow",
            authors="Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana",
            place=IPAW,
            other='Do not ignore other fields',
        ))
    """
    rules = rules or config.INFO_TO_INSERT
    info = copy(article)
    converter = ConvertDict(rules)
    return converter.run(info)


def set_by_info(work, info, set_scholar=True, rules=None):
    """Find attributes that should be modified in a work object to make it match an info object"""
    
    rules = rules or config.BIBTEX_TO_INFO
    rules.get("<set_before>", lambda x, y: None)(work, info)
    work_keys = {k for k in work.__dict__.keys() if not k.startswith("__")} - rules["<set_ignore_keys>"]
    meta_keys = info.keys() - rules.get("<set_ignore_keys>", set())
    show_result = OrderedDict(
        (key, None) for key in rules.get("<set_order>", [])
    )
    set_result = {}
    shared = meta_keys & work_keys
    for key in shared:
        value = info[key]
        add = False
        if key in rules.get("<set_ignore_but_show>", set()):
            add = True
        elif getattr(work, key) != value:
            add = True
            set_result[key] = value
        elif key in rules.get("<set_always_show>", set()):
            add = True
        if add:
            show_result[key] = (value, getattr(work, key))

    for key in meta_keys - work_keys:
        value = info[key]
        set_result[key] = value
        show_result[key] = (value, "")

    if set_scholar and rules.get("<scholar_ok>") and not hasattr(work, rules["<scholar_ok>"]):
        set_result[rules["<scholar_ok>"]] = True
    return {
        "show": show_result,
        "set": set_result,
    }


def changes_dict_to_set_attribute(metakey, changes_dict, end=";"):
    """Convert dictionart of changes to set_attribute instructions"""
    result = []
    for key, value in changes_dict.items():
        result.append("set_attribute({!r}, {!r}, {!r})".format(metakey, key, value))
    return "\n".join(result) + end


def citation_text(workref, cited, ref="", backward=False):
    """Create code for citation

    Arguments:

    * `workref` -- work varname that is cited (by default)

    * `cited` -- work info dict that cites the work (by default)

    Keyword arguments:

    * `ref` -- citation number

    * `backward` -- invert citation: `workref` cites `cited`


    Doctest:

    .. doctest::

        >>> print(citation_text('freire2008a', {'pyref': 'murta2014a'}))
        <BLANKLINE>
        DB(Citation(
            murta2014a, freire2008a, ref="",
            contexts=[
        <BLANKLINE>
            ],
        ))
        <BLANKLINE>

        >>> print(citation_text('pimentel2015a', {'pyref': 'murta2014a'}, backward=True, ref="[8]"))
        <BLANKLINE>
        DB(Citation(
            pimentel2015a, murta2014a, ref="[8]",
            contexts=[
        <BLANKLINE>
            ],
        ))
        <BLANKLINE>
    """
    pyref = dget(cited, "pyref")
    thepyref = pyref
    if backward:
        pyref, workref = workref, pyref
    return textwrap.dedent("""
    DB(Citation(
        {pyref}, {workref}, ref="{ref}",
        contexts=[

        ],
    ))
    """.format(**locals()))


def compare_paper_to_work(letter, key, work, paper):
    """Compares paper info to work

    Arguments:

    * `letter` -- indicates last letter

    * `key` -- indicates the key ID in BibTeX

    * `work` -- work object

    * `paper` -- paper info dict


    Returns: work, letter

    *  If it doesn't match, work is None

    Doctest:

    .. doctest::

        >>> reload()
        >>> work = work_by_varname('murta2014a')

        Fail:

        >>> paper = {'pyref': 'pimentel2017a', 'authors': 'Pimentel, Joao', 'name': 'Other', 'year': 2017}
        >>> compare_paper_to_work(ord("a") - 1, 'pimentel2017a', work, paper)
        (None, 98)
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper)
        (None, 96)

        Cluster ID:

        >>> paper['cluster_id'] = '5458343950729529273'
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper) == (work, 96)
        True

        Alias:

        >>> paper = {'pyref': 'chirigati2015a', 'authors': 'Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: Capturing and Analyzing Provenance of Scripts', 'year': 2015}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper) == (work, 96)
        True

        Name:

        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing and analyzing provenance of scripts', 'year': 2014}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper) == (work, 96)
        True

        Similar Name fail:

        >>> paper = {'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing provenance of scripts', 'year': 2014}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper)
        (None, 96)

        Similar Name works due to same place:

        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing provenance of scripts', 'year': 2014, 'place': 'IPAW'}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper) == (work, 96)
        True
    """
    if work is None:
        return None, letter
    if key.startswith(dget(paper, "pyref", "<invalid>")[:-1]):
        lastletter = key[-1] if key[-1].isalpha() else "a"
        letter = max(ord(lastletter) + 1, letter)

    if config.info_work_match(paper, work):
        dset(paper, "pyref", key)
        return work, letter

    return None, letter


def find_work_by_info(paper, pyrefs=None, rules=None):
    """Find work by paper info dict

    Limits search for specific year (or all years, if year is 0)

    Generates 'place' based on 'entrytype'

    Converts 'school' -> 'local'

    Tries to get varname from 'ID' in case the bibtex were generated from our db

    If it finds the work, it returns it

    Otherwise, it updates pyref and display to include a valid letter


    Doctest:

    .. doctest::

        >>> reload()
        >>> work = work_by_varname('murta2014a')
        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing and analyzing provenance of scripts', 'year': 2014}
        >>> find_work_by_info(paper) == work
        True
        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo', 'name': 'Other', 'year': 2014, 'display': 'murta'}
        >>> find_work_by_info(paper) is None
        True
        >>> paper['pyref']
        'murta2014b'
        >>> paper['display']
        'murta b'
    """
    rules = rules or config.FIND_INFO_WORK
    def update_old(old, new, rules):
        ignore = callable_get(rules, "<ignore>", [])
        for key, value in new.items():
            if key not in ignore:
                old[key] = value

    for key, value in rules.get("<skip>", []):
        if paper.get(key, "") == value:
            dset(paper, "pyref", "None")
            return None

    pyrefs = pyrefs or set()
    letter = ord("a") - 1

    convert = ConvertDict(rules)
    new_paper = convert.run(paper)
    old_paper, paper = paper, new_paper

    worklist = load_work_map(paper["_year"])

    if paper["_year"] == 0:
        worklist = load_work_map_all_years()

    if "_work" in paper:
        key = paper["_key"]
        work = paper["_work"]
        work, letter = compare_paper_to_work(letter, key, work, paper)
        if work:
            update_old(old_paper, paper, rules)
            return work

    for key, work in worklist:
        work, letter = compare_paper_to_work(letter, key, work, paper)
        if work:
            update_old(old_paper, paper, rules)
            return work

    for key in pyrefs:
        if dhas(paper, "pyref") and key.startswith(dget(paper, "pyref")):
            lastletter = key[-1] if key[-1].isalpha() else "a"
            letter = max(ord(lastletter) + 1, ord(letter))

    if letter != ord("a") - 1:
        letter = chr(letter)
        config.set_info_letter(paper, letter)

    update_old(old_paper, paper, rules)
    return None


def find_citation(citer, cited):
    """Find citation in the local database

    Returns the citation if the `citer` work cites the `cited` work

    Doctest:

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> freire2008a = work_by_varname("freire2008a")
        >>> pimentel2015a = work_by_varname("pimentel2015a")
        >>> citation = find_citation(murta2014a, freire2008a)
        >>> citation is None
        False
        >>> citation.ref
        '5'

        Not found:
        >>> citation = find_citation(pimentel2015a, freire2008a)
        >>> citation is None
        True
    """
    for citation in load_citations():
        if citation.work == citer and citation.citation == cited:
            return citation
    return None


def find_global_local_citation(citer, cited, file=None):
    """Find citations locally and globally for the works

    We use it to check if there is citation redefinition

    Doctest:

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> freire2008a = work_by_varname("freire2008a")
        >>> pimentel2015a = work_by_varname("pimentel2015a")
        >>> glo, loc = find_global_local_citation(murta2014a, freire2008a, "random")
        >>> glo is None
        False
        >>> glo.ref
        '5'
        >>> loc is None
        True
        >>> fname = "murta2014a"
        >>> glo, loc = find_global_local_citation(murta2014a, freire2008a, fname)
        >>> glo is None
        False
        >>> glo.ref
        '5'
        >>> loc is None
        False
        >>> loc is glo
        True
    """
    glob, loc = None, None
    for citation in load_citations():
        if citation.work == citer and citation.citation == cited:
            if file == citation._citations_file or not file:
                glob = loc = citation
                break
            else:
                glob = citation
    return glob, loc


def find_local_citation(wo1, wo2, backward, citation_file=None, warning=None):
    if backward:
        wo1, wo2 = wo2, wo1

    global_citation, local_citation = find_global_local_citation(
        wo1, wo2,
        file=citation_file
    )

    if global_citation and not local_citation and warning:
        warning("Duplicate citation: {} -> {}".format(
            oget(wo1, "metakey"),
            oget(wo2, "metakey"),
        ))
    
    return local_citation


def work_to_bibtex_entry(work, name=None, homogeneize=True, acronym=False, rules=None):
    """Convert work to BibTeX entry dict for bibtexparser

    Doctest:

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> result = work_to_bibtex_entry(murta2014a)
        >>> list(result)
        ['ID', 'address', 'publisher', 'pages', 'author', 'title', 'ENTRYTYPE', 'booktitle', 'year']
        >>> result['ID']
        'murta2014a'
        >>> result['address']
        'Cologne, Germany'
        >>> result['publisher']
        'Springer'
        >>> result['pages']
        '71--83'
        >>> result['booktitle']
        'International Provenance and Annotation Workshop'
        >>> result['author']  # doctest: +ELLIPSIS
        'Murta, Leonardo and Braganholo, Vanessa and ... and Freire, Juliana'
        >>> result['title']
        'no{W}orkflow: capturing and analyzing provenance of scripts'
        >>> result['year']
        '2014'
        >>> result['ENTRYTYPE']
        'inproceedings'

        Custom name:
        >>> result = work_to_bibtex_entry(murta2014a, name="other")
        >>> list(result)
        ['ID', 'address', 'publisher', 'pages', 'author', 'title', 'ENTRYTYPE', 'booktitle', 'year']
        >>> result['ID']
        'other'

        Use acronym for place name:
        >>> result = work_to_bibtex_entry(murta2014a, acronym=True)
        >>> list(result)
        ['ID', 'address', 'publisher', 'pages', 'author', 'title', 'ENTRYTYPE', 'booktitle', 'year']
        >>> result['booktitle']
        'IPAW'
    """
    converter = ConvertWork(rules or config.WORK_TO_BIBTEX)
    return converter.run(work, new=OrderedDict({
        "_name": name,
        "_acronym": acronym,
        "_homogeneize": homogeneize,
    }))


def work_to_bibtex(work, name=None, acronym=False, rules=None):
    """Convert work to bibtex text

    Doctest:

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> print(work_to_bibtex(murta2014a))
        @inproceedings{murta2014a,
          address = {Cologne, Germany},
          author = {Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana},
          booktitle = {International Provenance and Annotation Workshop},
          pages = {71--83},
          publisher = {Springer},
          title = {no{W}orkflow: capturing and analyzing provenance of scripts},
          year = {2014}
        }
        <BLANKLINE>
        <BLANKLINE>

        Custom name:

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> print(work_to_bibtex(murta2014a, name="other"))
        @inproceedings{other,
          address = {Cologne, Germany},
          author = {Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana},
          booktitle = {International Provenance and Annotation Workshop},
          pages = {71--83},
          publisher = {Springer},
          title = {no{W}orkflow: capturing and analyzing provenance of scripts},
          year = {2014}
        }
        <BLANKLINE>
        <BLANKLINE>

        Use acronym for place name:

        >>> print(work_to_bibtex(murta2014a, acronym=True))
        @inproceedings{murta2014a,
          address = {Cologne, Germany},
          author = {Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana},
          booktitle = {IPAW},
          pages = {71--83},
          publisher = {Springer},
          title = {no{W}orkflow: capturing and analyzing provenance of scripts},
          year = {2014}
        }
        <BLANKLINE>
        <BLANKLINE>
    """
    result = work_to_bibtex_entry(work, name=name, acronym=acronym, rules=rules)
    db = BibDatabase()
    db.entries = [result]

    writer = BibTexWriter()
    writer.indent = "  "
    return writer.write(db)


def match_bibtex_to_work(bibtex_str):
    """Find works by bibtex entries

    Returns a list of matches: (entry, work)

    Doctest:

    .. doctest::

        >>> reload()
        >>> bibtex = ''' @inproceedings{murta2014a,
        ...   address = {Cologne, Germany},
        ...   author = {Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana},
        ...   booktitle = {IPAW},
        ...   pages = {71--83},
        ...   publisher = {Springer},
        ...   title = {no{W}orkflow: capturing and analyzing provenance of scripts},
        ...   year = {2014}
        ... } '''
        >>> works = match_bibtex_to_work(bibtex)
        >>> murta2014a = work_by_varname("murta2014a")
        >>> works[0][1] is murta2014a
        True
    """
    entries = parse_bibtex(bibtex_str)
    return [
        (entry, find_work_by_info(bibtex_to_info(copy(entry))))
        for entry in entries
    ]


def find(text):
    """Find work by text in any of its attributes"""
    words = text.split()
    for work in load_work():
        match = True
        for word in words:
            if not any(word.lower() in str(getattr(work, attr)).lower() for attr in dir(work) if not attr.startswith("_")):
                match = False
                break
        if match:
            yield work


def find_line(work):
    """Find work position in file

    Arguments:

    * `work` -- work object

    Doctest:

    .. doctest::

        >>> from .operations import reload, work_by_varname
        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> find_line(murta2014a)
        6
    """
    import re
    with open(year_file(oget(work, "year")), "rb") as f:
        return [
            index
            for index, line in enumerate(f)
            if re.findall("(^{}\\s=)".format(oget(work, "metakey")).encode(), line)
        ][0] + 1


def invoke_editor(work):
    """Open work in a given line with the configured editor"""
    if not config.TEXT_EDITOR or not config.LINE_PARAMS:
        warnings.warn("You must set the config.TEXT_EDITOR and config.LINE_PARAMS to use this function")
        return
    subprocess.call([
        config.TEXT_EDITOR + " " +
        config.LINE_PARAMS.format(
            year_path=year_file(oget(work, "year")),
            line=find_line(work)
        ),
    ], shell=True)


def create_info_code(nwork, info, citation_var, citation_file, should_add, ref=""):
    """Create insertion code with both code and citation"""
    citations = ""
    text = "insert('''"
    if nwork is None:
        text += info_to_code(info) + "\n"
    if should_add["citation"] and citation_var:
        text += citation_text(
            citation_var, info,
            ref=ref, backward=should_add["backward"]
        ) + "\n"
        citations = ", citations='{}'".format(citation_file)
    text += "'''{});".format(citations)
    if text == "insert('''''');":
        text = ""

    if nwork and should_add["set"] and "(" not in dget(info, "pyref"):
        text += "\n" + changes_dict_to_set_attribute(dget(info, "pyref"), should_add["set"])

    return {
        "code": text.strip(),
        "extra": config.check_insertion(
            nwork, info, citation_var, citation_file, should_add, ref=""
        )
    }


def should_add_info(
    info, citation, article=None, backward=False, citation_file=None,
    warning=lambda x: None, set_scholar=False,
    article_rules=None, bibtex_rules=None,
    add_citation=True
):
    """Check if there is anything to add for this info"""
    convert = ConvertDict(article_rules or config.ARTICLE_TO_INFO)
    info = convert.run(info, article=article)
    nwork = consume(info, "_nwork")
    should_add = {
        "add": False,
        "citation": citation,
        "set": {},
        "backward": backward,
    }

    if not nwork or (not citation and add_citation):
        should_add["add"] = True
        should_add["citation"] = citation
        return should_add, nwork, info
    
    changes = set_by_info(nwork, info, set_scholar=set_scholar, rules=bibtex_rules or config.BIBTEX_TO_INFO)
    should_add["set"] = changes["set"]

    if should_add["set"]:
        should_add["add"] = True

    if add_citation:
        local_citation = find_local_citation(
            nwork, citation, backward,
            citation_file=citation_file, warning=warning
        )
        if local_citation:
            should_add["citation"] = None
        else:
            should_add["add"] = True

    return should_add, nwork, info


class Metakey(object):
    """Convert work or list of work to metakey

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> murta2014a @ Metakey()
        'murta2014a'
        >>> [murta2014a] @ Metakey()
        ['murta2014a']

    """
    def __rmatmul__(self, x):
        if hasattr(x, "__iter__"):
            return [y @ self for y in x]
        return oget(x, "metakey")


class MetakeyTitle(object):
    """Convert work or list of work to metakey - title

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> murta2014a @ MetakeyTitle()
        'murta2014a - noWorkflow: capturing and analyzing provenance of scripts'
        >>> [murta2014a] @ MetakeyTitle()
        ['murta2014a - noWorkflow: capturing and analyzing provenance of scripts']

    """
    
    def __rmatmul__(self, x):
        if hasattr(x, "__iter__"):
            return [y @ self for y in x]
        return "{} - {}".format(
            oget(x, "metakey"),
            oget(x, "name"),
        )


class WDisplay(object):
    """Convert work or list of work to display

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> murta2014a @ WDisplay()
        'no  Work  flow'
        >>> [murta2014a] @ WDisplay()
        ['no  Work  flow']

    """
    def __rmatmul__(self, x):
        if hasattr(x, "__iter__"):
            return [y @ self for y in x]
        return config.work_display(x)

metakey = Metakey()
metakey_title = MetakeyTitle()
wdisplay = WDisplay()


def check_config_deprecation():
    if hasattr(config, "WORK_BIBTEX_MAP"):
        warnings.warn(textwrap.dedent("""The configuration config.WORK_BIBTEX_MAP is not supported anymore.
        It was replaced by config.WORK_TO_BIBTEX, which is more complete.
        Please, modify it according to your needs
        """))
    if hasattr(config, "FORM_BUTTONS"):
        old_form_to_new(show_deprecation=True)

