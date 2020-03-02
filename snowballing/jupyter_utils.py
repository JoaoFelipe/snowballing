"""This module provides useful jupyter widgets"""
import base64
import os
import warnings

from ipywidgets import DOMWidget, HBox, Label, Text, Button
from IPython.display import display, Javascript
from urllib.parse import quote

from .dbindex import year_file
from .operations import invoke_editor, metakey
from . import config



def display_cell(text):
    """Remove cells that start with "# Temp" and add a new one

    Arguments:

    * `text` -- new cell content

    """
    encoded_code = base64.b64encode(quote(text.encode()).encode()).decode()
    display(Javascript("""
        $('span:contains("# Temp")').closest('.cell').remove();
        var code = IPython.notebook.insert_cell_{0}('code');
        code.set_text(decodeURIComponent(window.atob("{1}")));
    """.format('below', encoded_code)))


def idisplay(*args, label=True):
    """Display multiple values using ipywidget HBox

    Arguments:

    * `*args` -- list of values

    Keyword arguments:

    * `label` -- create a Label widget instead of a Text widget, if value is
      not a widget

    """
    new_widget = lambda x: Label(x) if label else Text(value=x)
    args = [
        arg if isinstance(arg, DOMWidget) else new_widget(arg)
        for arg in args
    ]
    display(HBox(args))


def new_button(description, function):
    """Create a new Button widget and set its on_click callback"""
    button = Button(description=description)
    button.on_click(function)
    return button


def work_button(work, description=None):
    """Create a button for the work with a link to the editor

    Arguments:

    * `work` -- the work object

    Keyword arguments:

    * `description` -- button label. It uses the work varname if it is not
      specified
    """
    def click(w):
        invoke_editor(work)

    return new_button(description or work @ metakey, click)
