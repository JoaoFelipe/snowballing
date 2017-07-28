"""This module contains functions to :meth:`~reload` the database, load work and 
citations from there, and operate BibTeX"""

import importlib
import re
import textwrap

from copy import copy
from collections import OrderedDict
from string import ascii_lowercase
import bibtexparser

from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from bibtexparser.customization import homogeneize_latex_encoding
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase


from .models import DB, Year
from .dbindex import parse_varname, places_file

from . import models, config
from .utils import import_submodules, consume, setitem, compare_str, match_any

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
    places = config.MODULES['places']
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
    DB.clear_work()
    DB.clear_citations()


def _reload_work():
    """Reload work and create WORD_CACHE"""
    for key, module in import_submodules(config.MODULES['work']).items():
        yname = key.split('.')[-1]
        fname = (yname + '.py')
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
        >>> from example.database.work.y2014 import murta2014a
        >>> murta2014a.metakey
        'murta2014a'
        >>> from example.database.work.y2015 import murta2014a as alias
        >>> alias is murta2014a
        True
    """
    _clear_db()
    importlib.reload(config.MODULES['places'])
    _reload_work()
    import_submodules(config.MODULES['citations'])
    import_submodules(config.MODULES['groups'])

    for key, work in load_work_map_all_years():
        aliases = []
        work.metakey = key
        if hasattr(work, 'alias'):
            aliases = [work.alias]
        if hasattr(work, 'aliases'):
            aliases = work.aliases
        for alias in aliases:
            year = alias[0]
            module = "y{}.py".format(year) if isinstance(year, int) else year
            if module not in WORK_CACHE:
                module = "y9999.py"
            setattr(WORK_CACHE[module], key, work)


def bibtex_to_info(citation):
    """Convert BibTeX dict from bibtexparse to info dict for adding a db entry 

    It has the following conversions:

    * title -> name (required)
    
    * author -> authors (required)
        
    * year -> year (0 if not specified)
            
      * If there is '[in press]', creates 'note' with 'in press'
    
    * journal/booktitle -> place1 ('' if not specified)
            
      * If 'place1' matches a place in the database, creates also 'place'
    
    * pages -> pp
    
    * ENTRYTYPE -> entrytype

    Also creates the following fields:
    
    * display -- Last name of first author
    
    * pyref -- {display}{year}{letter}


    Doctest:

    .. doctest::

        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 0, 'place1': '', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'year': '2017'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 2017, 'place1': '', 'display': 'pim', 'pyref': 'pim2017a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'year': '2017 [in press]'})
        {'name': 'a', 'authors': 'Pim, J', 'note': 'in press', 'year': 2017, 'place1': '', 'display': 'pim', 'pyref': 'pim2017a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'pages': '1--5'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 0, 'pp': '1--5', 'place1': '', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'journal': 'CiSE'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 0, 'place1': 'CiSE', 'place': 'CiSE', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'ENTRYTYPE': 'article'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 0, 'place1': '', 'entrytype': 'article', 'display': 'pim', 'pyref': 'pim0a'}
        >>> bibtex_to_info({'title': 'a', 'author': 'Pim, J', 'other': 'a'})
        {'name': 'a', 'authors': 'Pim, J', 'year': 0, 'place1': '', 'display': 'pim', 'pyref': 'pim0a', 'other': 'a'}
    """
    result = {}
    setitem(result, "name", consume(citation, "title"))
    setitem(result, "authors", consume(citation, "author"))
    
    if "[in press]" in citation.get("year", ""):
        setitem(result, "note", "in press")
        citation["year"] = citation["year"][:4]
    setitem(result, "year", int(consume(citation, "year") or 0))
    setitem(result, "pp", consume(citation, "pages"))
    setitem(result, "place1", consume(citation, "journal") or
            consume(citation, "booktitle") or "")
    setitem(result, "entrytype", consume(citation, "ENTRYTYPE"))

    set_place(result)
    set_display(result)
    set_pyref(result)

    for key, value in citation.items():
        setitem(result, key, value)

    return result


def set_display(info, check_existence=False):
    """Set displays of info based on the authors field

    Selects the last name of the first author

    Doctest:

    .. doctest::

        >>> info = {'authors': 'Pimentel, Joao'}; set_display(info)
        >>> info['display']
        'pimentel'
        >>> info = {'authors': 'Pimentel, Joao and Braganholo, Vanessa'}
        >>> set_display(info)
        >>> info['display']
        'pimentel'
        >>> info = {'authors': 'Joao Pimentel'}
        >>> set_display(info)
        >>> info['display']
        'pimentel'
        >>> info = {'authors': 'Joao Pimentel and Vanessa Braganholo'}
        >>> set_display(info)
        >>> info['display']
        'pimentel'
        >>> info = {'authors': 'Joao Pimentel, Vanessa Braganholo'}
        >>> set_display(info)
        >>> info['display']
        'pimentel'
        """
    if check_existence and 'display' in info:
        return
    authors = info['authors']
    if ' and ' in authors:
        authors = authors.split(' and ')[0]
    if ',' not in authors:
        last = authors.split()[-1]
    else:
        last = re.findall(r'(\w*)[`\-=~!@#$%^&*()_+\[\]{};\'\\:"|<,/<>?]', authors)[0]
    setitem(info, "display", last.lower())


def set_pyref(info, check_existence=False):
    """Set pyref of info. Finds the next available letter in the database 

    Doctest:

    .. doctest::

        >>> info = {'display': 'pimentel', 'year': 2017}
        >>> set_pyref(info)
        >>> info['pyref']
        'pimentel2017a'
        >>> info = {'display': 'pimentel', 'year': 2015}
        >>> set_pyref(info)
        >>> info['pyref']
        'pimentel2015b'
    """
    if check_existence and 'pyref' in info:
        return
    pyref = "{display}{year}".format(**info)
    for letter in ascii_lowercase:
        if not work_by_varname(pyref + letter):
            break
    pyref += letter
    setitem(info, "pyref", pyref)


def set_place(info, check_existence=False):
    """Set place of info 

    It reorders common patterns:

    * Proceedings of the
    * International Conference on
    * International Convention on
    * International Symposium on

    Then, it removes numbers and it tries to match places in the database.

    It considers a match if the matching ratio for the place name 
    is >= config.SIMILARITY_RATIO (0.8).

    It also considers a match if the acronym matches.

    Doctest:

    .. doctest::

        >>> info = {"place1": "IPAW"}
        >>> set_place(info)
        >>> info["place"]
        'IPAW'
        >>> info = {"place1": "Software Engineering, International Conference on"}
        >>> set_place(info)
        >>> info["place"]
        'ICSE'
        >>> info = {"place1": "A random conference"}
        >>> set_place(info)
        >>> 'place' not in info
        True
    """
    if check_existence and 'place' in info:
        return
    import re
    place = info["place1"].replace("Proceedings of the ", "")
    place = re.sub(r"(?<=[0-9])(?:st|nd|rd|th)", "", place)
    place = re.sub(r"(.*) (International Conference on)", r"\2 \1", place, flags=re.I)
    place = re.sub(r"(.*) (International Convention on)", r"\2 \1", place, flags=re.I)
    place = re.sub(r"(.*) (International Symposium on)", r"\2 \1", place, flags=re.I)
    place = ''.join([i for i in place if not i.isdigit()])
    
    maxmatch = max(
        (max(
            compare_str(place, varvalue.name),
            1 if place == varvalue.acronym else 0
        ), varname, varvalue) for varname, varvalue in load_places_vars()
    )

    if maxmatch[0] >= config.SIMILARITY_RATIO or maxmatch[2].name in place:
        setitem(info, "place", maxmatch[1])


def extract_info(article):
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
        {'name': 'noWorkflow: capturing and analyzing provenance of scripts', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'year': 2014, 'pp': '71--83', 'place1': 'International Provenance and Annotation Workshop', 'entrytype': 'inproceedings', 'place': 'IPAW', 'display': 'murta', 'pyref': 'murta2014b', 'organization': 'Springer', 'ID': 'murta2014noworkflow', 'excerpt': 'Abstract', 'cluster_id': '5458343950729529273', 'scholar': 'http://scholar.google.com/scholar?cites=5458343950729529273&as_sdt=2005&sciodt=0,5&hl=en'}
    """
    parser = BibTexParser()
    parser.customization = convert_to_unicode
    as_citation = article.as_citation()
    if not isinstance(as_citation, str):
        as_citation = as_citation.decode("utf-8")
    citation = bibtexparser.loads(as_citation, parser=parser).entries[0]
    result = bibtex_to_info(citation)
    setitem(result, "excerpt", article.attrs["excerpt"][0])
    setitem(result, "cluster_id", article.attrs["cluster_id"][0])
    setitem(result, "scholar", article.attrs["url_citations"][0])
    setitem(result, "div", article.div)
    return result

   
def info_to_code(article):
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
        <BLANKLINE>
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
        <BLANKLINE>
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
            other="Do not ignore other fields",
        ))
    """
    info = copy(article)
    work_type = consume(info, "_work_type") or "Work"
    year = consume(info, "year")
    name = consume(info, "name")
    authors = consume(info, "authors")
    display = consume(info, "display")
    pyref = consume(info, "pyref")
    place = consume(info, "place")
    may_be_related_to = consume(info, "may_be_related_to")
    due = consume(info, "due")
    consume(info, "excerpt")
    other = ""
    if place is not None:
        consume(info, "place1")
        func = str if isinstance(place, str) else repr
        other += 'place={},\n        '.format(func(place))

    other += "\n        ".join('{}="{}",'.format(key, value.replace('"', r'\"'))
                          for key, value in info.items())
        
    result = """
    {pyref} = DB({work_type}(
        {year}, "{name}",\n""".format(**locals())
    if due is not None:
        result += '        due="{}",\n'.format(due)
    if may_be_related_to:
        result += '        may_be_related_to=[{}],\n'.format(
            ', '.join('"{}"'.format(e) for e in may_be_related_to.split(','))
        )
    result += """        display="{display}",
        authors="{authors}",
        {other}
    ))""".format(**locals())
    return textwrap.dedent(result)


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
    pyref = cited["pyref"]
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

        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing provenance of scripts', 'year': 2014}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper)
        (None, 96)

        Similar Name works due to same place:

        >>> paper = {'pyref': 'murta2014a', 'authors': 'Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana', 'name': 'noWorkflow: capturing provenance of scripts', 'year': 2014, 'place': 'IPAW'}
        >>> compare_paper_to_work(ord("a") - 1, 'other2017a', work, paper) == (work, 96)
        True
    """
    if work is None:
        return None, letter
    if key.startswith(paper.get("pyref", '<invalid>')[:-1]):
        lastletter = key[-1] if key[-1].isalpha() else "a"
        letter = max(ord(lastletter) + 1, letter)

    if hasattr(work, "cluster_id") and "cluster_id" in paper and work.cluster_id == paper["cluster_id"]:
        paper["pyref"] = key
        return work, letter
    aliases = []
    if hasattr(work, "alias"):
        aliases = [work.alias]
    if hasattr(work, "aliases"):
        aliases = work.aliases
    for alias in aliases:
        if alias[0] == paper["year"] and alias[1] == paper["name"]:
            if len(alias) > 2 and alias[2] == paper["authors"] or work.authors == paper["authors"]:
                paper["pyref"] = key
                return work, letter

    required = 0.90 + (0.1 if paper["year"] == 0 else 0)
    if "place" in paper:
        place = getattr(config.MODULES['places'], paper["place"], None)
        if place is not None and place.name == work.place.name:
            required -= 0.1

    if work is None:
        return None, letter
    if compare_str(work.name, paper["name"]) > required:
        paper["pyref"] = key
        return work, letter

    return None, letter


def find_work_by_info(paper, pyrefs=None):
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

    if paper.get('_work_type', '') == 'Site':
        paper['pyref'] = "None"
        return None

    pyrefs = pyrefs or set()
    letter = ord("a") - 1

    worklist = load_work_map(paper["year"])

    if paper["year"] == 0:
        worklist = load_work_map_all_years()

    if paper.get("entrytype") in ("phdthesis", "mastersthesis"):
        paper["place"] = "Thesis"

    if paper.get("entrytype") == "techreport":
        paper["place"] = "TechReport"

    if paper.get("entrytype") == "book":
        paper["place"] = "Book"

    if "school" in paper:
        paper["local"] = paper["school"]
        del paper["school"]

    if "ID" in paper:
        key = paper["ID"]
        work = work_by_varname(key)
        work, letter = compare_paper_to_work(letter, key, work, paper)
        if work:
            return work
        
    for key, work in worklist:
        work, letter = compare_paper_to_work(letter, key, work, paper)
        if work:
            return work
        

    for key in pyrefs:
        if "pyref" in paper and key.startswith(paper["pyref"]):
            lastletter = key[-1] if key[-1].isalpha() else "a"
            letter = max(ord(lastletter) + 1, ord(letter))

    if letter != ord("a") - 1:
        letter = chr(letter)
        if paper["pyref"][-1].isalpha():
            paper["pyref"] = paper["pyref"][:-1]
        paper["pyref"] += letter
        paper["display"] += " " + letter

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
            if file == citation._citations_file or file is None:
                glob = loc = citation
                break
            else:
                glob = citation
    return glob, loc


def work_to_bibtex_entry(work, name=None, homogeneize=True, acronym=False):
    """Convert work to BibTeX entry dict for bibtexparser

    Doctest:

    .. doctest::

        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> result = work_to_bibtex_entry(murta2014a)
        >>> list(result)
        ['ID', 'address', 'publisher', 'pages', 'booktitle', 'author', 'title', 'year', 'ENTRYTYPE']
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
        ['ID', 'address', 'publisher', 'pages', 'booktitle', 'author', 'title', 'year', 'ENTRYTYPE']
        >>> result['ID']
        'other'

        Use acronym for place name:
        >>> result = work_to_bibtex_entry(murta2014a, acronym=True)
        >>> list(result)
        ['ID', 'address', 'publisher', 'pages', 'booktitle', 'author', 'title', 'year', 'ENTRYTYPE']
        >>> result['booktitle']
        'IPAW'
    """
    options = config.WORK_FIELDS
    ignore = config.BIBTEX_IGNORE_FIELDS
    mapa = config.WORK_BIBTEX_MAP
    if not name:
        if hasattr(work, 'metakey'):
            name = work.metakey
        else:
            split = work.authors.split()
            name = split[0].replace(",", "") if split else "a"
            name += str(work.year)

    if config.DEBUG_FIELDS:
        for key in dir(work):
            if not match_any(key, options) and not match_any(key, ignore):
                print(work.display, work.year, key)

    result = OrderedDict()
    result["ID"] = name
    for key in reversed(options):
        if hasattr(work, key) and not match_any(key, ignore):
            value = getattr(work, key)
            is_conference = (
                key == "place" and acronym and
                value.type == "Conference" and not value.acronym.startswith("<")
            )
            if is_conference:
                value = value.acronym
            name = mapa.get(key, lambda x: key)(work)
            if name:
                result[name] = str(value)
    if not "ENTRYTYPE" in result:
        result["ENTRYTYPE"] = "misc"
    if hasattr(work, "notes"):
        result["year"] += " [{}]".format(work.notes)
    if homogeneize:
        result = homogeneize_latex_encoding(result)
    return result


def work_to_bibtex(work, name=None, acronym=False):
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
    result = work_to_bibtex_entry(work, name=name, acronym=acronym)
    db = BibDatabase()
    db.entries = [result]

    writer = BibTexWriter()
    writer.indent = '  '
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
    parser = BibTexParser()
    parser.customization = convert_to_unicode
    entries = bibtexparser.loads(bibtex_str, parser=parser).entries
    for entry in entries:
        entry['title'] = entry['title'].replace('{', '').replace('}', '')
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
