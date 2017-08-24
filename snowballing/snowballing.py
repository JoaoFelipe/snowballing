"""This module provides tools to analyze the snowballing and widgets to perform
and curate the snowballing"""
import base64
import re
import json
import traceback
import sys

from contextlib import contextmanager
from collections import defaultdict, namedtuple, Counter, OrderedDict
from copy import copy
from urllib.parse import urlparse, parse_qs
from itertools import zip_longest

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from IPython.utils.py3compat import str_to_bytes, bytes_to_str
from IPython.display import clear_output, display, HTML, Javascript
from ipywidgets import HBox, VBox, IntSlider, ToggleButton, Text
from ipywidgets import Dropdown, Button, Tab, Label, Textarea, Output

from .jupyter_utils import display_cell
from .operations import consume, find_work_by_info, find_global_local_citation
from .operations import set_pyref, bibtex_to_info
from .operations import load_citations, reload, info_to_code, citation_text
from .operations import work_by_varname, set_display, extract_info, set_place
from .scholar import ScholarConf
from .models import Site

from . import config

Step = namedtuple("Step", "name new_references new_related total_visited total_related")

@contextmanager
def snowballing(initial_set, filter_function=None):
    """Context manager for helping producing snowballing provenance

    By default, the filter_function selects work with "snowball" category

    Returns backward, forward, log, visited:

    * backward is a function that expands the frontier following backward refs

    * forward is a function that expands the frontier following forward refs

    * log is a list of steps

    * visited is a set of references
    """
    if filter_function is None:
        filter_function = lambda x: x.category == "snowball"

    reload()
    ref = defaultdict(list)
    rev_ref = defaultdict(list)
    for cit in load_citations():
        ref[cit.work].append(cit.citation)
        rev_ref[cit.citation].append(cit.work)

    visited = copy(initial_set)
    related = copy(initial_set)
    size = len(initial_set)
    log = [Step("start", size, size, size, size)]

    def backward(frontier):
        new_frontier = set()
        last_visited_size = len(visited)
        for work in frontier:
            for cited in ref[work]:
                visited.add(cited)
                if filter_function(cited):
                    new_frontier.add(cited)
                    related.add(cited)
        new_frontier -= frontier
        log.append(Step(
            "backward", len(visited) - last_visited_size,
            len(new_frontier), len(visited), len(related)
        ))
        return new_frontier

    def forward(frontier):
        new_frontier = set()
        last_visited_size = len(visited)
        for work in frontier:
            for citer in rev_ref[work]:
                visited.add(citer)
                if filter_function(citer):
                    new_frontier.add(citer)
                    related.add(citer)

        new_frontier -= frontier
        log.append(Step(
            "forward", len(visited) - last_visited_size,
            len(new_frontier), len(visited), len(related)
        ))

        return new_frontier

    yield backward, forward, log, visited


def create_provenance(initial_set, filter_function=None, backward_first=True):
    """Produce snowballing provenance

    Arguments:

    * `initial_set` -- start set of the snowballing

    Keyword arguments:

    * `filter_function` -- function for filtering results

      * By default it selects work with category == 'snowball'

    * `backward_first` -- order of the snowball

      * By default it applies backward snowballing first


    Returns: frontier, log, visited


    Doctest:

    .. doctest::

        >>> from .operations import reload, work_by_varname
        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> frontier, log, visited = create_provenance({murta2014a})
        >>> len(frontier)
        1
        >>> len(log)
        3
        >>> log[0]
        Step(name='start', new_references=1, new_related=1, total_visited=1, total_related=1)
        >>> log[1]
        Step(name='backward', new_references=1, new_related=0, total_visited=2, total_related=1)
        >>> log[2]
        Step(name='forward', new_references=1, new_related=0, total_visited=3, total_related=1)
        >>> len(visited)
        3

        Forward first:

        >>> from .operations import reload, work_by_varname
        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> frontier, log, visited = create_provenance({murta2014a}, backward_first=False)
        >>> len(frontier)
        1
        >>> len(log)
        3
        >>> log[0]
        Step(name='start', new_references=1, new_related=1, total_visited=1, total_related=1)
        >>> log[1]
        Step(name='forward', new_references=1, new_related=0, total_visited=2, total_related=1)
        >>> log[2]
        Step(name='backward', new_references=1, new_related=0, total_visited=3, total_related=1)
        >>> len(visited)
        3
    """
    frontier = copy(initial_set)
    with snowballing(frontier, filter_function) as (backward, forward, log, visited):
        order = [backward, forward]
        if not backward_first:
            order = [forward, backward]
        new_frontier = frontier
        count = 0
        while count < 2:
            for func in order:
                count = count + 1 if not new_frontier else 0
                if count >= 2:
                    break
                new_frontier = func(frontier)
                frontier.update(new_frontier)
    return frontier, log, visited


def log_to_provn(log):
    """Convert log of steps (produced by the snowballing function) into provn

    Doctest:

    .. doctest::

        >>> from .operations import reload, work_by_varname
        >>> reload()
        >>> murta2014a = work_by_varname("murta2014a")
        >>> frontier, log, visited = create_provenance({murta2014a}, backward_first=False)
        >>> print(log_to_provn(log))
        document
          default <http://example.org/>
        <BLANKLINE>
          activity(start, -, -)
          entity(s0, [type="Set", length="1"])
          wasGeneratedBy(g0; s0, start, -)
        <BLANKLINE>
          activity(forward1, -, -, [found="1", related="0"])
          used(u0; forward1, s0, -)
        <BLANKLINE>
          activity(backward1, -, -, [found="1", related="0"])
          used(u1; backward1, s0, -)
        <BLANKLINE>
        endDocument
    """
    set_id = -1
    current_set = 0
    result = ["document", "  default <http://example.org/>", ""]
    actions = Counter()

    for step in log:
        new_set = False

        # activity
        if step.name == "start":
            activity_id = "start"
            extra = ""
        else:
            actions[step.name] += 1
            activity_id = "{}{}".format(step.name, actions[step.name])
            extra = ', [found="{}", related="{}"]'.format(step.new_references, step.new_related)
        result.append("  activity({}, -, -{})".format(activity_id, extra))

        # used
        if set_id != -1:
            used_id = "u{}".format(actions["used"])
            actions["used"] += 1
            result.append('  used({}; {}, s{}, -)'.format(used_id, activity_id, set_id))
        else:
            used_id = "-"

        # entity
        if step.total_related != current_set:
            set_id += 1
            new_set = True
            current_set = step.total_related
            result.append('  entity(s{}, [type="Set", length="{}"])'.format(set_id, current_set))
            generated_id = "g{}".format(actions["generated"])
            actions["generated"] += 1
            result.append('  wasGeneratedBy({}; s{}, {}, -)'.format(generated_id, set_id, activity_id))
            if used_id != "-":
                result.append('  wasDerivedFrom(s{}, s{}, {}, {}, {}, [prov:type="prov:Revision"])'.format(
                    set_id, set_id - 1, activity_id, generated_id, used_id
                ))
        result.append('')

    result.append("endDocument")
    return '\n'.join(result)


class Converter:
    """Convert texts into other formats

    Four modes are available:

    * BibTeX

      * Converts bibtex to a json for inserting the reference

    * Text

      * Removes line breaks and diacricts from text. Use it to copy text from
        pdf documents

    * [N] author name place other year

      * Converts references in this format to a json for inserting the
        reference

      * Consider each space as a line break

      * The "other" field can be created using multiple (or 0) lines

        * It also can define the attribute names using 'attr=value'

        * For example::

              [1]
              Pimentel, João Felipe and Braganholo, Vanessa and Murta, Leonardo and Freire, Juliana
              Tracking and analyzing the evolution of provenance from scripts
              IPAW
              pp=16--28
              Springer
              2016

              [2]
              ...

    * Quoted

      * Surrounds text with quotation marks and add spaces to fit the citation
    """

    def __init__(self, mode="text"):
        self.mode_widget = Dropdown(
            options={
                'BibTeX': 'bibtex',
                'Text': 'text',
                '[N] author name place other year': 'citation',
                'Quoted': 'quoted',
            },
            value=mode
        )
        self.button_widget = Button(
            description="Set article_list variable",
            disabled=mode not in ("citation", "bibtex")
        )
        self.frompdf_widget = Textarea()
        self.output_widget = Textarea()
        self.label_widget = Label()
        self.frompdf_widget.observe(self.write)
        self.mode_widget.observe(self.select)
        self.button_widget.on_click(self.set_variable)
        self.view = VBox([
            HBox([self.mode_widget, self.button_widget, self.label_widget]),
            HBox([self.frompdf_widget, self.output_widget])
        ])

        self.frompdf_widget.layout.height = "500px"
        self.output_widget.layout.height = "500px"
        self.frompdf_widget.layout.width = "50%"
        self.output_widget.layout.width = "50%"
        self.backup = ""
        self.ipython = get_ipython()

    def write(self, b):
        """ Writes right column according to selected mode """
        getattr(self, self.mode_widget.value)(b)

    def select(self, b):
        """ Selects new mode. Use previous output as input """
        self.backup = self.frompdf_widget.value
        self.frompdf_widget.value = self.output_widget.value
        self.button_widget.disabled = self.mode_widget.value not in ("citation", "bibtex")

    def quoted(self, b):
        """ Adds quotes to value. Use it for citation """
        self.label_widget.value = ""
        inputpdf = self.frompdf_widget.value
        result = "".join(re.split(r'[\r\n]+', inputpdf.strip()))
        result = '"{}",\n        '.format(result)
        self.output_widget.value = result

    def text(self, b):
        """ Removes line breaks and diacricts """
        self.label_widget.value = ""
        inputpdf = self.frompdf_widget.value
        result = "".join(re.split(r'[\r\n]+', inputpdf.strip()))
        result = (result
            .replace("ﬀ", "ff")
            .replace("ﬁ", "fi")
            .replace("ﬂ", "fl")
            .replace("ﬃ", "ffi")
            .replace("ﬄ", "ffl")
            .replace("–", "--")
            .replace("—", "---")
            .replace(". doi:", "\ndoi=")
        )
        self.output_widget.value = result

    def citation(self, b):
        """ Produces a json based on the format [N] author name place other year """
        inputpdf = self.frompdf_widget.value
        elements = inputpdf.split("\n\n")
        jresult = []
        incomplete = 0
        for element in elements:
            lines = element.strip().split('\n')

            # '[N] author name place other year'
            info = OrderedDict()
            info['citation_id'] = lines[0].strip()
            if lines[-1].strip().startswith('>') and len(lines) >= 2:
                info['pyref'] = lines[-1][1:].strip()
                other = lines[1:-1]
                info['_work_type'] = "Ref"
            elif lines[-1].strip().startswith('http') and len(lines) >= 3:
                info['name'] = lines[1].strip()
                info['url'] = lines[-1].strip()
                info['_work_type'] = "Site"
                other = lines[2:-1]
            elif len(lines) >= 5 and lines[-1].strip().isnumeric():
                info['authors'] = lines[1].strip()
                info['name'] = lines[2].strip()
                info['place1'] = lines[3].strip()
                info['year'] = int(lines[-1].strip())
                info['_work_type'] = "Work"
                other = lines[4:-1]
            else:
                jresult.append("Incomplete")
                incomplete += 1
                continue
            for num, line in zip(range(1, 10000), other):
                line = line.strip()
                splitted = line.split('=')
                if len(splitted) > 1:
                    info[splitted[0]] = '='.join(splitted[1:])
                else:
                    info['other{}'.format(num)] = line
            jresult.append(info)
        self.label_widget.value = str(len(jresult) - incomplete)
        self.output_widget.value = json.dumps(jresult, indent=2)

    def bibtex(self, b):
        """ Produces a json based on a bibtex """
        inputpdf = self.frompdf_widget.value
        jresult = []
        incomplete = 0
        parser = BibTexParser()
        parser.customization = convert_to_unicode
        for entry in bibtexparser.loads(inputpdf, parser=parser).entries:
            try:
                info = bibtex_to_info(entry)
                info['_work_type'] = "Work"
                info['name'] = info['name'].replace('{', '').replace('}', '')
                jresult.append(info)
            except Exception:
                jresult.append("Incomplete")
                incomplete += 1
        self.label_widget.value = str(len(jresult) - incomplete)
        self.output_widget.value = json.dumps(jresult, indent=2)

    def set_variable(self, b):
        """ Creates variable 'article_list' with resulting JSON """
        self.ipython.user_ns['article_list'] = [
            x for x in json.loads(self.output_widget.value)
            if x != "Incomplete"
        ]

    def browser(self):
        """ Presents the widget """
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        display(self.view)


class ArticleNavigator:
    """Navigate on article list for insertion"""

    def __init__(self, citation_var=None, citation_file=None, articles=None, backward=True, force_citation_file=True):
        reload()
        self.force_citation_file = force_citation_file
        self.citation_var = citation_var
        self.citation_file = citation_file or citation_var
        self.disable_show = False
        self.work = work_by_varname(citation_var) if citation_var else None
        self.backward = backward
        self.to_display = []
        self.custom_widgets = []

        self.next_article_widget = Button(
            description='Next Article', icon='fa-caret-right')
        self.previous_article_widget = Button(
            description='Previous Article', icon='fa-caret-left')
        self.selector_widget = IntSlider(value=0, min=0, max=20, step=1)
        self.reload_article_widget = Button(
            description='Reload Article', icon='fa-refresh')

        self.file_field_widget = ToggleButton(value=False, description="File")
        self.due_widget = Text(value="", description="Due")
        self.place_widget = Text(value="", description="Place")
        self.year_widget = Text(value="", description="Year")
        self.prefix_widget = Text(value="", description="Prefix Var")
        self.pdfpage_widget = Text(value="", description="PDFPage")

        self.work_type_widget = Dropdown(
            options=[tup[0] for tup in config.CLASSES],
            value=config.DEFAULT_CLASS,
            description="Type"
        )
        self.article_number_widget = Label(value="")
        self.output_widget = Output()

        self.next_article_widget.on_click(self.next_article)
        self.previous_article_widget.on_click(self.previous_article)
        self.selector_widget.observe(self.show)
        self.reload_article_widget.on_click(self.show)

        self.due_widget.observe(self.write_due)
        self.place_widget.observe(self.write_place)

        widgets = [
            self.work_type_widget, self.file_field_widget,
            self.due_widget, self.place_widget,
            self.year_widget, self.prefix_widget,
            self.pdfpage_widget,
        ]

        hboxes = [
            HBox([
                self.previous_article_widget,
                self.reload_article_widget,
                self.next_article_widget
            ]),
        ]

        for row in config.FORM_BUTTONS:
            hboxes.append(HBox([self.create_custom_button(tup) for tup in row]))

        for tup in config.FORM_TEXT_FIELDS:
            self.create_custom_text(tup)

        widgets += self.custom_widgets

        iterable = iter(widgets)
        for w1, w2 in zip_longest(iterable, iterable):
            hboxes.append(HBox([w1] + ([w2] if w2 else [])))


        hboxes.append(HBox([
            self.reload_article_widget,
            self.selector_widget,
            self.article_number_widget
        ]))

        hboxes.append(self.output_widget)

        self.view = VBox(hboxes)

        self.set_articles(articles)
        self.erase_article_form()

    def create_custom_text(self, tup):
        """Create custom text based on config.FORM_TEXT_FIELDS tuple"""
        text = Text(value="", description=tup[0])
        text._workattr = tup[1]
        self.custom_widgets.append(text)
        if tup[2]:
            if hasattr(self, tup[2]):
                warnings.warn("ArticleNavigator already has the attribute {}. Skipping".format(tup[2]))
            else:
                setattr(self, tup[2], text)
        return text

    def create_custom_button(self, tup):
        """Create custom button based on config.FORM_BUTTONS tuple"""
        button = Button(description=tup[0])
        def function(b):
            for key, value in tup[1].items():
                getattr(self, key).value = value
            self.show(clear=True)
        button.on_click(function)
        return button

    def set_articles(self, articles):
        """Set list of articles and restart slider"""
        self.articles = list(self.valid_articles(articles))
        self.disable_show = True
        self.selector_widget.value = 0
        self.selector_widget.max = max(len(self.articles) - 1, 0)
        self.next_article_widget.disabled = self.selector_widget.value == self.selector_widget.max
        self.previous_article_widget.disabled = self.selector_widget.value == 0
        self.article_number_widget.value = "{}/{}".format(
            min(self.selector_widget.value + 1, len(self.articles)),
            len(self.articles)
        )
        self.disable_show = False

    def erase_article_form(self):
        """Erases form fields"""
        self.article_number_widget.value = "{}/{}".format(
            min(self.selector_widget.value + 1, len(self.articles)),
            len(self.articles)
        )
        self.file_field_widget.value = False
        self.due_widget.value = ""
        self.place_widget.value = ""
        self.year_widget.value = ""
        self.work_type_widget.value = "Work"
        self.prefix_widget.value = ""
        self.pdfpage_widget.value = ""
        for widget in self.custom_widgets:
            widget.value = ""

    def write_due(self, b=None):
        """Write event for due_widget"""
        if self.due_widget.value and self.work_type_widget.value == "Work":
            self.work_type_widget.value = "WorkUnrelated"
        elif not self.due_widget.value and self.work_type_widget.value == "WorkUnrelated":
            self.work_type_widget.value = "Work"

    def write_place(self, b=None):
        """Write event for place_widget"""
        if self.place_widget.value == "Lang" and self.work_type_widget.value == "Work":
            self.work_type_widget.value = "WorkLang"

    def next_article(self, b=None):
        """Next article click event"""
        self.selector_widget.value = min(self.selector_widget.value + 1, self.selector_widget.max)
        self.erase_article_form()
        self.show(clear=True)

    def previous_article(self, b=None):
        """Previous article click event"""
        self.selector_widget.value = max(self.selector_widget.value - 1, self.selector_widget.min)
        self.erase_article_form()
        self.show(clear=True)

    def valid_articles(self, articles, show=False):
        """Generate valid articles"""
        if not articles:
            return
        for article in articles:
            info = copy(article)
            consume(info, 'div')
            consume(info, 'citation_id')

            if info.get('_work_type') == 'Site':
                info['pyref'] = 'Site("{name}", "{url}")'.format(**info)
                nwork = Site(info['name'], info['url'])
            elif info.get('_work_type') == 'Ref':
                nwork = work_by_varname(info['pyref'])
                article['name'] = info['name'] = nwork.name
                article['place'] = info['place'] = nwork.place.name
            else:
                set_display(info, check_existence=True)
                set_pyref(info, check_existence=True)
                set_place(info, check_existence=True)
                nwork = find_work_by_info(info, set())

            if not self.work:
                yield article, nwork, info
                continue
            wo1, wo2 = nwork, self.work
            if self.backward:
                wo1, wo2 = wo2, wo1
            if nwork is None:
                yield article, nwork, info
                continue
            global_citation, local_citation = find_global_local_citation(
                wo1, wo2,
                file=self.citation_file if self.force_citation_file else None
            )
            if global_citation and not local_citation and show:
                self.to_display.append("Duplicate citation")

            if not local_citation:
                yield article, nwork, info
                continue

    def clear(self):
        """Clear cell and output"""
        if self.disable_show:
            return
        self.to_display = []
        display(Javascript(
            """$('span:contains("# Temp")').closest('.cell').remove();"""))
        self.output_widget.clear_output()

    def update_info(self, info, field, widget, value=None, default=""):
        """Update info according to widget"""
        if widget.value != default:
            info[field] = widget.value if value is None else value
        return bool(widget.value)

    def show_site(self, article, nwork, info):
        """Display site citation"""
        text = "# Temp\n"
        text += "insert('''"
        text += citation_text(
            self.citation_var, info,
            ref=article.get('citation_id', ''),
            backward=self.backward
        ) + "\n"
        text += "''', citations='{}');".format(self.citation_file)
        display_cell(text)
        self.output_widget.clear_output()
        with self.output_widget:
            if self.to_display:
                display("\n".join(self.to_display))
            if 'div' in article:
                display(HTML(repr(article['div'])))
            elif 'name' in article:
                print(article['name'])
        self.to_display = []

    def show_article(self, article, nwork, info):
        """Display article"""
        citations = ""
        text = "# Temp\n"
        text += "insert('''"
        if nwork is None:
            text += info_to_code(info) + "\n"
        if self.citation_var:
            text += citation_text(
                self.citation_var, info,
                ref=article.get('citation_id', ''),
                backward=self.backward
            ) + "\n"
            citations = ", citations='{}'".format(self.citation_file)
        text += "'''{});".format(citations)

        if nwork:
            for key, value in info.items():
                if key in {'pyref', 'place1', '_work_type'}:
                    continue
                if not hasattr(nwork, key):
                    text += "\nset_attribute('{}', '{}', '{}');".format(
                        info['pyref'], key, value
                    )
        display_cell(text)
        self.output_widget.clear_output()
        with self.output_widget:
            if self.to_display:
                display("\n".join(self.to_display))
            if 'div' in article:
                display(HTML(repr(article['div'])))
            elif 'name' in article:
                print(article['name'])
            display(HTML("<input value='{}.pdf' style='width: 100%'></input>".format(info['pyref'])))
            if not 'place' in info:
                display(HTML("<input value='{}' style='width: 100%'></input>".format(info['place1'])))
        self.to_display = []

    def show(self, b=None, clear=True):
        """Generic display"""
        _up = self.update_info
        reload()
        self.next_article_widget.disabled = self.selector_widget.value == self.selector_widget.max
        self.previous_article_widget.disabled = self.selector_widget.value == 0
        if clear:
            self.clear()
        if self.disable_show or not self.articles:
            return
        article, _, _ = self.articles[self.selector_widget.value]
        with self.output_widget:
            if 'div' in article:
                display(HTML(repr(article['div'])))
            else:
                print(article['name'])
        for article, nwork, info in self.valid_articles([article], show=True):
            if info.get("_work_type") == "Site":
                self.show_site(article, nwork, info)
                continue
            if info.get("place", "") == "Lang":
                self.work_type_widget.value = "WorkLang"
            _up(info, 'due', self.due_widget)
            _up(info, 'place', self.place_widget)
            _up(info, "_work_type", self.work_type_widget, default="Work")

            if _up(info, 'year', self.year_widget) or _up(info, 'display', self.prefix_widget):
                set_pyref(info)
            _up(info, 'file', self.file_field_widget, info["pyref"] + ".pdf", default=False)
            _up(info, 'file', self.pdfpage_widget, info.get("file", "") + "#page={}".format(self.pdfpage_widget.value))

            for widget in self.custom_widgets:
                _up(info, widget._workattr, widget)

            self.show_article(article, nwork, info)

    def browser(self):
        """Widget visualization"""
        with self.output_widget:
            print("Press 'Reload Article'")
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        with self.output_widget:
            print("Press 'Reload Article'")
        display(self.view)


class BackwardSnowballing(ArticleNavigator):
    """Navigate on article list for insertion with backward citation"""

    def __init__(self, citation_var, citation_file=None, articles=None, force_citation_file=True):
        work = work_by_varname(citation_var)
        citation_file = citation_file or getattr(work, "citation_file", citation_var)
        super(BackwardSnowballing, self).__init__(
            citation_var=citation_var,
            citation_file=citation_file,
            articles=articles,
            backward=True,
            force_citation_file=force_citation_file
        )


class ForwardSnowballing:
    """Navigate on article list for insertion with forward citation"""

    def __init__(self, querier, citation_var, citation_file=None, debug=False, start=None, load=True):
        from .selenium_scholar import URLQuery
        reload()
        self.querier = querier
        work = work_by_varname(citation_var)
        citation_file = citation_file or getattr(work, "citation_file", citation_var)
        self.navigator = ArticleNavigator(citation_var, citation_file, backward=False, force_citation_file=False)
        self.query = URLQuery(self.navigator.work.scholar, start)
        self.next_page_widget = Button(description='Next Page', icon='fa-arrow-right')
        self.reload_widget = Button(description='Reload', icon='fa-refresh')
        self.previous_page_widget = Button(description='Previous Page', icon='fa-arrow-left')
        self.debug_widget = ToggleButton(value=debug, description="Debug")
        self.page_number_widget = Label(value="")
        self.next_page_widget.on_click(self.next_page)
        self.reload_widget.on_click(self.reload)
        self.previous_page_widget.on_click(self.previous_page)

        self.view = Tab([
            VBox([
                HBox([
                    self.previous_page_widget,
                    self.reload_widget,
                    self.next_page_widget,
                    self.debug_widget,
                    self.page_number_widget
                ]),
                self.navigator.output_widget,
            ]),
            self.navigator.view
        ])
        self.view.set_title(0, "Page")
        self.view.set_title(1, "Article")
        if load:
            self.reload(None)

    def next_page(self, b):
        """ Gets next page from scholar """
        self.query = self.querier.result.next_page
        self.reload(b)

    def previous_page(self, b):
        """ Gets previous page from scholar """
        self.query = self.querier.result.prev_page
        self.reload(b)

    def reload(self, b, show=True):
        """ Reloads page """
        self.navigator.output_widget.clear_output()
        if self.debug_widget.value:
            ScholarConf.LOG_LEVEL = 3
        else:
            ScholarConf.LOG_LEVEL = 2
        reload()
        with self.navigator.output_widget:
            self.querier.tasks.clear()
            self.querier.send_query(self.query)
            self.page_number_widget.value = parse_qs(urlparse(
                self.query.get_url()).query
            ).get('start', ['0'])[0]

            self.navigator.set_articles(map(extract_info, self.querier.result.articles))

        self.next_page_widget.disabled = self.querier.result.next_page is None
        self.previous_page_widget.disabled = self.querier.result.prev_page is None

    def browser(self):
        """ Presents widget """
        with self.navigator.output_widget:
            print("Click on 'Article' and press 'Reload Article'")
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        with self.navigator.output_widget:
            print("Click on 'Article' and press 'Reload Article'")
        display(self.view)


class ScholarUpdate:
    """Widget for curating database"""

    def __init__(self, querier, worklist, force=False, debug=False, index=0):
        reload()
        self.worklist = worklist
        self.force = force
        self.querier = querier
        self.next_page_widget = Button(description='Next Work', icon='fa-arrow-right')
        self.reload_widget = Button(description='Reload', icon='fa-refresh')
        self.previous_page_widget = Button(description='Previous Work', icon='fa-arrow-left')
        self.debug_widget = ToggleButton(value=debug, description="Debug")
        self.textarea_widget = ToggleButton(value=False, description="TextArea")
        self.page_number_widget = Label(value="")
        self.output_widget = Output()
        self.next_page_widget.on_click(self.next_page)
        self.reload_widget.on_click(self.reload)
        self.previous_page_widget.on_click(self.previous_page)
        self.textarea_widget.observe(self.show)
        self.view = VBox([
            HBox([
                self.previous_page_widget,
                self.reload_widget,
                self.next_page_widget,
                self.debug_widget,
                self.textarea_widget,
                self.page_number_widget
            ]),
            self.output_widget
        ])
        self.index = index
        self.varname = ""
        self.work = None
        self.articles = []
        self.reload(show=False)


    def next_page(self, b):
        """Go to next page"""
        self.index = min(len(self.worklist) - 1, self.index + 1)
        self.reload(b)

    def previous_page(self, b):
        """Go to previous page"""
        self.query = max(0, self.index - 1)
        self.reload(b)

    def set_index(self):
        """Set page index"""
        self.page_number_widget.value = str(self.index)
        self.next_page_widget.disabled = self.index == len(self.worklist) - 1
        self.previous_page_widget.disabled = self.index == 0

    def show(self, b=None):
        """Show comparison"""
        self.output_widget.clear_output()
        with self.output_widget:
            if not self.articles:
                print(self.varname, "<unknown>")
                return
            try:
                print(self.varname, getattr(self.work, "scholar_ok", False))
                var, work, articles = self.varname, self.work, self.articles
                meta = extract_info(articles[0])
                table = "<table>{}</table>"
                if not hasattr(work, 'entrytype'):
                    work.entrytype = work.place.type
                tool = {'y', 'x', 'i', 'display', 'pyref', "place", 'ID', 'year_index', 'file', 'excerpt', 'div'}
                if "place" in meta and not "place1" in meta:
                    meta["place1"] = meta["place"]
                work.place1 = "{} ({})".format(work.place.name, work.place.acronym)

                keys = {k for k in work.__dict__.keys() if not k.startswith("__")} - tool
                meta_keys = meta.keys() - tool
                order = {"name": 0, "authors": 1, "entrytype": 2, "place1": 3, "year": 4}
                rows = ["<tr><th></th><th>{}</th><th>{}</th></tr>".format(var, "Scholar")]
                sets = []
                shared = sorted(list(meta_keys & keys), key=lambda x: (order.get(x, len(order)), x))
                for key in shared:
                    value = str(meta[key])
                    add = False
                    if key in ('place1', 'year'): # Always show. Don't replace
                        add = True
                    elif getattr(work, key) != value: # Show changes
                        add = True
                        sets.append("set_attribute('{}', '{}', '{}')".format(var, key, value))
                    elif key in order: # Always show. Replace
                        add = True
                    if add:
                        rows.append("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(key, getattr(work, key), value))
                for key in meta_keys - keys:
                    value = str(meta[key])
                    rows.append("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(key, "", value))
                    sets.append("set_attribute('{}', '{}', '{}')".format(var, key, value))

                if not hasattr(work, "scholar_ok"):
                    sets.append("set_attribute('{}', 'scholar_ok', True)".format(var))
                sets.append("None")
                textarea = ""
                if self.textarea_widget.value:
                    textarea = "<textarea rows='{}' style='width: 100%'>{}</textarea>".format(len(rows), "\n".join(sets))
                else:
                    display_cell("# Temp\n"+ "\n".join(sets))
                display(HTML(table.format("".join(rows))+"<br>"+textarea))
            except:
                traceback.print_exc(file=sys.stdout)
                print(self.varname, '<error>')

    def reload(self, b=None, show=True):
        """Reload"""
        self.output_widget.clear_output()
        with self.output_widget:
            if self.debug_widget.value:
                ScholarConf.LOG_LEVEL = 3
            else:
                ScholarConf.LOG_LEVEL = 2
            reload()
            self.querier.tasks.clear()

            if self.index >= len(self.worklist):
                self.set_index()
                return
            self.varname = self.worklist[self.index]
            self.work = work_by_varname(self.varname)
            print(self.varname, getattr(self.work, "scholar_ok", False))
            if getattr(self.work, "scholar_ok", False) and not self.force:
                self.set_index()
                return
            from .selenium_scholar import SearchScholarQuery
            query = SearchScholarQuery()

            query.set_scope(False)
            query.set_words(self.work.name + " " + self.work.authors)
            query.set_num_page_results(1)
            self.querier.send_query(query)

            self.articles = self.querier.articles
        if show:
            self.show()

        self.set_index()

    def browser(self):
        """Present widget"""
        self.show()
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        self.show()
        display(self.view)
