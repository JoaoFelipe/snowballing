"""This module provides tools to analyze the snowballing and widgets to perform
and curate the snowballing"""
import re
import json
import traceback
import sys
import os
import subprocess

from copy import copy
from urllib.parse import urlparse, parse_qs

from IPython.display import clear_output, display, HTML, Javascript
from ipywidgets import HBox, VBox, IntSlider, ToggleButton, Text, Layout
from ipywidgets import Dropdown, Button, Tab, Label, Textarea, Output, FileUpload

from .collection_helpers import oset, dset, oget, consume
from .jupyter_utils import display_cell
from .operations import bibtex_to_info, reload, citation_text, work_by_varname
from .operations import extract_info, create_info_code, should_add_info
from .operations import set_by_info, changes_dict_to_set_attribute
from .scholar import ScholarConf
from .rules import old_form_to_new
from .utils import display_list, parse_bibtex

from . import config


def form_definition():
    if not hasattr(config, "FORM_BUTTONS"):
        form = copy(config.FORM)
        consume(form, "<tags>")
        return form
    return old_form_to_new(True)


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

    def __init__(self, mode=None):
        options={
            "BibTeX": "bibtex",
            "Text": "text",
            "[N] author name place other year": "citation",
            "Quoted": "quoted",
        }

        if config.PDF_EXTRACTOR:
            options["PDF"] = "pdf"
            mode = mode or "pdf"

        mode = mode or "text"
        self.mode_widget = Dropdown(
            options=options,
            value=mode
        )
        self.button_widget = Button(
            description="Set article_list variable",
            disabled=mode not in ("citation", "bibtex")
        )
        self.frompdf_widget = Textarea()
        self.output_widget = Textarea()
        self.label_widget = Label()
        self.frompdf_widget.observe(self.write, names="value")
        self.mode_widget.observe(self.select, names="value")
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
        self.select_mode(mode)

    def write(self, b):
        """ Writes right column according to selected mode """
        getattr(self, self.mode_widget.value)(b)

    def select_mode(self, mode):
        """ Selects new mode. Use previous output as input """
        self.backup = self.frompdf_widget.value
        self.frompdf_widget.value = self.output_widget.value
        self.button_widget.disabled = mode not in ("citation", "bibtex")

    def select(self, change):
        """ Selects new mode. Use previous output as input """
        self.select_mode(change.new)

    def quoted(self, change):
        """ Adds quotes to value. Use it for citation """
        self.label_widget.value = ""
        inputpdf = change.new
        result = "".join(re.split(r"[\r\n]+", inputpdf.strip()))
        result = '"{}",\n        '.format(result)
        self.output_widget.value = result

    def text(self, change):
        """ Removes line breaks and diacricts """
        self.label_widget.value = ""
        inputpdf = change.new
        result = "".join(re.split(r"[\r\n]+", inputpdf.strip()))
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

    def citation(self, change):
        """ Produces a json based on the format [N] author name place other year """
        inputpdf = change.new
        elements = inputpdf.split("\n\n")
        jresult = []
        incomplete = 0
        for element in elements:
            info = config.convert_citation_text_lines_to_info(element)
            jresult.append(info)
            if info == "Incomplete":
                incomplete += 1
                
        self.label_widget.value = str(len(jresult) - incomplete)
        self.output_widget.value = json.dumps(jresult, indent=2)

    def bibtex(self, change):
        """ Produces a json based on a bibtex """
        inputpdf = change.new
        jresult = []
        incomplete = 0
        for entry in parse_bibtex(inputpdf):
            try:
                info = bibtex_to_info(entry, config.BIBTEX_TO_INFO_WITH_TYPE)
                jresult.append(info)
            except Exception:
                jresult.append("Incomplete")
                incomplete += 1
        self.label_widget.value = str(len(jresult) - incomplete)
        self.output_widget.value = json.dumps(jresult, indent=2)

    def pdf(self, change):
        """ Extracts citations from pdf """
        filename = self.frompdf_widget.value.strip()
        if filename.startswith("file://"):
            filename = filename[len("file://"):]
        self.label_widget.value = "Processing"
        if os.path.isfile(filename):
            cmd = config.PDF_EXTRACTOR.format(path=filename)
            try:
                stdout = subprocess.check_output(cmd, shell=True)
                self.output_widget.value = stdout.decode("utf-8")
            except subprocess.CalledProcessError as e:
                self.output_widget.value = "Exception: {!r}".format(e)
        else:
            self.output_widget.value = "Invalid Path"
        self.label_widget.value = ""


    def set_variable(self, b):
        """ Creates variable 'article_list' with resulting JSON """
        self.ipython.user_ns["article_list"] = [
            x for x in json.loads(self.output_widget.value)
            if x != "Incomplete"
        ]

    def browser(self):
        """ Presents the widget """
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        display(self.view)


WIDGET_CLS = {
    "text": lambda x: Text(value=x[3] or "", description=x[1]),
    "toggle": lambda x: ToggleButton(value=x[3] or False, description=x[1]),
    "dropdown": lambda x: Dropdown(options=x[4], value=x[3] or "", description=x[1]),
    "button": lambda x: Button(description=x[1]),
}


class EventRunner:
    
    def __init__(self, navigator, info=None):
        self.widgets = navigator.widgets
        self.widgets_empty = navigator.widgets_empty
        self.navigator = navigator
        self.info = info
        self.operations = {
            "if": self.op_if,
            "and": self.op_and,
            "or": self.op_or,
            "==": self.op_eq,
            "!=": self.op_neq,
            ">": self.op_gt,
            ">=": self.op_ge,
            "<": self.op_lt,
            "<=": self.op_le,
            "not": self.op_not,
            "+": self.op_plus,
            "reload": self.op_reload,
            "pyref": self.op_pyref,
            "update_info": self.op_update_info,
        }
        
    def access_attr(self, attr):
        if isinstance(attr, str):
            if attr.startswith(":"):
                return self.widgets[attr[1:]].value
            if self.info is not None and attr.startswith("."):
                return self.info.get(attr[1:], "")
            attr = attr.replace(r"\.", ".").replace(r"\:", ":")
            return attr
        else:
            return self.execute(attr)
        
    def set_attr(self, attr, value):
        self.widgets[attr].value = value
        return value
        
    
    def op_if(self, event):
        condition = self.execute(event[0])
        if condition:
            return self.execute(event[1])
        else:
            return self.execute(event[2])
        
    def op_and(self, event):
        for op in event:
            if not self.execute(op):
                return False
        return True
    
    def op_or(self, event):
        for op in event:
            if self.execute(op):
                return True
        return False
    
    def op_eq(self, event):
        return self.access_attr(event[0]) == self.access_attr(event[1])
    
    def op_neq(self, event):
        return self.access_attr(event[0]) != self.access_attr(event[1])
    
    def op_gt(self, event):
        return self.access_attr(event[0]) > self.access_attr(event[1])
    
    def op_ge(self, event):
        return self.access_attr(event[0]) >= self.access_attr(event[1])
    
    def op_lt(self, event):
        return self.access_attr(event[0]) < self.access_attr(event[1])
    
    def op_le(self, event):
        return self.access_attr(event[0]) <= self.access_attr(event[1])
    
    def op_not(self, event):
        return not self.access_attr(event[0])
    
    def op_plus(self, event):
        result = self.access_attr(event[0])
        for element in event[1:]:
            result += self.access_attr(element)
        return result

    def op_reload(self, event):
        self.navigator.show(clear=True)
    
    def op_pyref(self, event):
        dset(self.info, "pyref", config.info_to_pyref(self.info))
        
    def op_update_info(self, event):
        value = self.access_attr(event[2])
        default = self.access_attr(event[3])
        widget_value = self.access_attr(event[1])
        if widget_value != default:
            self.info[event[0]] = widget_value if value is None else value
        return bool(widget_value)
        
    def execute(self, event):
        if isinstance(event, list):
            if event and isinstance(event[0], str):
                if event[0] not in self.operations:
                    print("Error: Event", event[0], "not found")
                else:
                    return self.operations[event[0]](event[1:])
            else:
                return [
                    self.execute(inst) for inst in event
                ]
        elif isinstance(event, dict):
            for key, value in event.items():
                self.set_attr(key, self.access_attr(value))
            return "="
        else:
            return event


class WebWidget:

    def __init__(self, value):
        self.value = value


class WebNavigator:

    def __init__(self, form_values, nwork, info, citation_var=None, citation_file=None, backward=True, should_add=None):
        self.info = info
        self.nwork = nwork
        self.should_add = should_add
        self.citation_var = citation_var
        self.citation_file = citation_file or oget(should_add["citation"], "citation_file", citation_var)
        self.backward = backward

        self.widgets = {}
        self.widgets_empty = {}
        self.form_values = form_values

        form = form_definition()
        for widget in form["widgets"]:
            self.widgets[widget[2]] = WebWidget(None)
            if len(widget) >= 4:
                self.widgets[widget[2]].value = self.widgets_empty[widget[2]] = widget[3]
        
        for attr, value in form_values.items():
            self.widgets[attr].value = value

        self.show_event = form["show"]

    def show(self, clear=True):
        runner = EventRunner(self, info=self.info)
        runner.execute(self.show_event)

        result = create_info_code(
            self.nwork, self.info,
            self.citation_var, self.citation_file,
            self.should_add
        )
        result["widgets_update"] = {}
        for attr, value in self.form_values.items():
            if self.widgets[attr].value != value:
                result["widgets_update"][attr] = self.widgets[attr].value

        return result


class RunWidget:

    def __init__(self):
        from ipywidgets import Button
        self.code = Textarea()
        self.execute = Button(description="Run")
        self.clear_btn = Button(description="Clear")
        self.output = Output()
        self.exec_count = Label("[ ]")
        self.execute.layout.width = "60px"
        self.execute.layout.height = "50px"
        self.clear_btn.layout.width = "60px"
        self.clear_btn.layout.height = "50px"
        self.code.layout.width = "550px"
        self.code.rows = 6
        self.view = VBox([
            HBox([
                VBox([
                    self.execute, 
                    self.clear_btn,
                    self.exec_count
                ]),
                self.code
            ]),
            self.output
        ])
        self.execute.on_click(self.click)
        self.clear_btn.on_click(self.clear_click)
        self.ipython = get_ipython()

    def clear(self):
        self.code.value = ""
        self.code.rows = 6
        self.exec_count.value = "[ ]"

    def set_code(self, code):
        self.code.value = code
        self.code.rows = max(len(code.split("\n")) + 1, 6)
        self.exec_count.value = "[ ]"

    def click(self, b):
        with self.output:
            result = self.ipython.run_cell(self.code.value, store_history=True)
            self.exec_count.value = "[{}]".format(result.execution_count or " ")

    def clear_click(self, b):
        self.output.clear_output()
        self.clear()


class ReplaceCellWidget:

    def __init__(self):
        self.view = Label()

    def clear(self):
        display(Javascript(
            """$('span:contains("# Temp")').closest('.cell').remove();"""))

    def set_code(self, code):
        text = "# Temp\n" + code
        display_cell(text)


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
            description="Next Article", icon="fa-caret-right")
        self.previous_article_widget = Button(
            description="Previous Article", icon="fa-caret-left")
        self.selector_widget = IntSlider(value=0, min=0, max=20, step=1)
        self.reload_article_widget = Button(
            description="Reload Article", icon="fa-refresh")

        
        self.article_number_widget = Label(value="")
        self.output_widget = Output()

        self.next_article_widget.on_click(self.next_article)
        self.previous_article_widget.on_click(self.previous_article)
        self.selector_widget.observe(self.show)
        self.reload_article_widget.on_click(self.show)
        
        self.widgets = {}
        self.widgets_empty = {}
        
        form = form_definition()
        for widget in form["widgets"]:
            if widget[0] not in WIDGET_CLS:
                print("Error: Widgets type {} not found".format(widget[0]))
            else:
                self.widgets[widget[2]] = WIDGET_CLS[widget[0]](widget)
            if len(widget) >= 4:
                self.widgets_empty[widget[2]] = widget[3]
        
        for event in form["events"]:
            if event[1] == "observe":
                self.widgets[event[0]].observe(self.process(event))
            if event[1] == "click":
                self.widgets[event[0]].on_click(self.process(event))
                
        self.show_event = form["show"]

        hboxes = [
            HBox([
                self.previous_article_widget,
                self.reload_article_widget,
                self.next_article_widget
            ]),
        ]
        
        for widgets in form["order"]:
            hboxes.append(HBox([
                self.widgets[widget] for widget in widgets
            ]))

        hboxes.append(HBox([
            self.reload_article_widget,
            self.selector_widget,
            self.article_number_widget
        ]))

        hboxes.append(self.output_widget)

        self.runner_widget = RunWidget() if config.RUN_WIDGET else ReplaceCellWidget() 
        hboxes.append(self.runner_widget.view)
        self.view = VBox(hboxes)

        self.set_articles(articles)
        self.erase_article_form()

    def process(self, event):
        runner = EventRunner(self)
        def action(b):
            runner.execute(event[2])
        return action
    
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
        for key, widget in self.widgets.items():
            if key in self.widgets_empty:
                if isinstance(widget, ToggleButton):
                    widget.value = self.widgets_empty[key] or False 
                else:   
                    widget.value = self.widgets_empty[key] or ""

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
            should, nwork, info = should_add_info(
                article, self.work, article=article,
                backward=self.backward,
                citation_file=self.citation_file if self.force_citation_file else None,
                warning=lambda x: self.to_display.append(x)
            )
            if should["add"]:
                yield article, nwork, info, should

    def clear(self):
        """Clear cell and output"""
        if self.disable_show:
            return
        self.to_display = []
        self.runner_widget.clear()
        self.output_widget.clear_output()

    def update_info(self, info, field, widget, value=None, default=""):
        """Update info according to widget"""
        if widget.value != default:
            info[field] = widget.value if value is None else value
        return bool(widget.value)

    def show_article(self, article, nwork, info, should):
        """Display article"""
        result = create_info_code(
            nwork, info,
            self.citation_var, self.citation_file, should,
            ref=article.get("_ref", "")
        )
        self.runner_widget.set_code(result["code"])
        self.output_widget.clear_output()
        with self.output_widget:
            if self.to_display:
                display("\n".join(self.to_display))
            display_list(config.display_article(article))
            for key, value in result["extra"].items():
                display(HTML("<label>{}</label><input value='{}' style='width: 100%'></input>".format(key, value)))
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
        article, _, _, _ = self.articles[self.selector_widget.value]
        with self.output_widget:
            display_list(config.display_article(article))
        for article, nwork, info, should in self.valid_articles([article], show=True):
            runner = EventRunner(self, info=info)
            runner.execute(self.show_event)
            self.show_article(article, nwork, info, should)

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
        citation_file = citation_file or oget(work, "citation_file", citation_var)
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
        citation_file = citation_file or oget(work, "citation_file", citation_var)
        self.navigator = ArticleNavigator(citation_var, citation_file, backward=False, force_citation_file=False)
        self.query = URLQuery(self.navigator.work.scholar, start)
        self.next_page_widget = Button(description="Next Page", icon="fa-arrow-right")
        self.reload_widget = Button(description="Reload", icon="fa-refresh")
        self.previous_page_widget = Button(description="Previous Page", icon="fa-arrow-left")
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
            ).get("start", ["0"])[0]

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

    def __init__(self, querier, worklist, force=False, debug=False, index=0, rules=None):
        reload()
        self.rules = rules or config.BIBTEX_TO_INFO
        self.worklist = worklist
        self.force = force
        self.querier = querier
        self.next_page_widget = Button(description="Next Work", icon="fa-arrow-right")
        self.reload_widget = Button(description="Reload", icon="fa-refresh")
        self.previous_page_widget = Button(description="Previous Work", icon="fa-arrow-left")
        self.debug_widget = ToggleButton(value=debug, description="Debug")
        self.textarea_widget = ToggleButton(value=False, description="TextArea")
        self.page_number_widget = Label(value="")
        self.output_widget = Output()
        self.next_page_widget.on_click(self.next_page)
        self.reload_widget.on_click(self.reload)
        self.previous_page_widget.on_click(self.previous_page)
        self.textarea_widget.observe(self.show)
        self.runner_widget = RunWidget() if config.RUN_WIDGET else ReplaceCellWidget()
        self.view = VBox([
            HBox([
                self.previous_page_widget,
                self.reload_widget,
                self.next_page_widget,
                self.debug_widget,
                self.textarea_widget,
                self.page_number_widget
            ]),
            self.output_widget,
            self.runner_widget.view,
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
                print(self.varname, getattr(self.work, self.rules.get(
                    "<scholar_ok>", "_some_invalid_attr_for_scholar_ok"
                ), False))
                var, work, articles = self.varname, self.work, self.articles
                meta = extract_info(articles[0])
                table = "<table>{}</table>"
                rows = ["<tr><th></th><th>{}</th><th>{}</th></tr>".format(var, "Scholar")]
                changes = set_by_info(work, meta, rules=self.rules)
                set_text = changes_dict_to_set_attribute(var, changes["set"])
                for key, value in changes["show"].items():
                    if value is not None:
                        meta_value, work_value = value
                        rows.append("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                            key, work_value, meta_value
                        ))
                textarea = ""
                if self.textarea_widget.value:
                    textarea = "<textarea rows='{}' style='width: 100%'>{}</textarea>".format(len(rows), set_text)
                else:
                    self.runner_widget.set_code(set_text)
                display(HTML(table.format("".join(rows))+"<br>"+textarea))
            except:
                traceback.print_exc(file=sys.stdout)
                print(self.varname, "<error>")

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
            print(self.varname, oget(self.work, "scholar_ok", False, cvar=config.SCHOLAR_MAP))
            if oget(self.work, "scholar_ok", False, cvar=config.SCHOLAR_MAP) and not self.force:
                self.set_index()
                return
            from .selenium_scholar import SearchScholarQuery
            query = SearchScholarQuery()

            query.set_scope(False)
            query.set_words(config.query_str(self.work))
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


class SearchScholar:
    """Search Scholar and Navigate on article list for insertion"""

    def __init__(self, querier, debug=False):
        from snowballing.selenium_scholar import URLQuery
        reload()
        self.querier = querier

        self.query = None
        self.search_text_widget = Text(value="", layout=Layout(width="99%"))
        self.do_search_widget = Button(description="Search", icon="fa-search")

        self.navigator = ArticleNavigator(force_citation_file=False)
        self.next_page_widget = Button(description="Next Page", icon="fa-arrow-right")
        self.reload_widget = Button(description="Reload", icon="fa-refresh")
        self.previous_page_widget = Button(description="Previous Page", icon="fa-arrow-left")
        self.debug_widget = ToggleButton(value=debug, description="Debug")
        self.page_number_widget = Label(value="")
        self.next_page_widget.on_click(self.next_page)
        self.reload_widget.on_click(self.reload)
        self.previous_page_widget.on_click(self.previous_page)
        self.do_search_widget.on_click(self.search)
        self.search_text_widget.on_submit(self.search)


        self.tab_widget = Tab([
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
        self.view = VBox([
            self.search_text_widget,
            self.do_search_widget,
            self.tab_widget
        ])

        self.tab_widget.set_title(0, "Page")
        self.tab_widget.set_title(1, "Article")

    def search(self, b):
        from .selenium_scholar import SearchScholarQuery
        self.query = SearchScholarQuery()
        self.query.set_scope(False)
        self.query.set_words(self.search_text_widget.value)
        #self.query.set_num_page_results(20)
        self.reload(b)

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
            ).get("start", ["0"])[0]

            self.navigator.set_articles(map(extract_info, self.querier.result.articles))
            self.navigator.show()
            self.tab_widget.selected_index = 1

        self.next_page_widget.disabled = self.querier.result.next_page is None
        self.previous_page_widget.disabled = self.querier.result.prev_page is None

    def browser(self):
        """ Presents widget """
        with self.navigator.output_widget:
            print("Search and press 'Reload Article'")
        return self.view

    def _ipython_display_(self):
        """ Displays widget """
        with self.navigator.output_widget:
            print("Search and press 'Reload Article'")
        display(self.view)

