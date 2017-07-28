""" jupyter_utils provides useful jupyter widgets """ 
import base64
import os
import subprocess
import warnings

from ipywidgets import DOMWidget, HBox, Label, Text, Button
from IPython.display import display, Javascript
from IPython.utils.py3compat import str_to_bytes, bytes_to_str

from .dbindex import year_file
from . import config


def display_cell(text):
    """ Removes cells that start with "# Temp" and adds a new one with :text """
    encoded_code = bytes_to_str(base64.b64encode(str_to_bytes(text)))
    display(Javascript("""
        $('span:contains("# Temp")').closest('.cell').remove();
        var code = IPython.notebook.insert_cell_{0}('code');
        code.set_text(atob("{1}"));
    """.format('below', encoded_code)))


def idisplay(*args, label=True):
    """ Displays multiple values using ipywidget HBox """
    new_widget = lambda x: Label(x) if label else Text(value=x)
    args = [
        arg if isinstance(arg, DOMWidget) else new_widget(arg)
        for arg in args
    ]
    display(HBox(args))


def find_line(work):
    """ Finds work position in file 

    Doctest
    >>> from .operations import reload, work_by_varname
    >>> reload()
    >>> murta2014a = work_by_varname("murta2014a")
    >>> find_line(murta2014a)
    6
    """
    import re
    with open(year_file(work.year), 'rb') as f:
        return [
            index
            for index, line in enumerate(f)
            if re.findall('(^{}\\s=)'.format(work.metakey).encode(), line)
        ][0] + 1
  

def invoke_editor(work):
    """ Opens work in a given line with the configured editor """
    if not config.TEXT_EDITOR or not config.LINE_PARAMS:
        warnings.warn("You must set the config.TEXT_EDITOR and config.LINE_PARAMS to use this function")
        return
    subprocess.call([
        config.TEXT_EDITOR,
        config.LINE_PARAMS.format(
            year_path=year_file(work.year),
            line=find_line(work)
        ),
    ])


def new_button(description, function):
    """ Creates a new Button widget and sets its on_click callback """
    button = Button(description=description)
    button.on_click(function)
    return button


def work_button(work, description=None):
    """ Creates a button for the work with a link to the editor """
    def click(w):
        invoke_editor(work)
    
    return new_button(description or work.metakey, click)
