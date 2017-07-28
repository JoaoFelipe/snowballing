""" dbindex includes helper functions to identify the location of database files
and extract information from the convention we use for varnames
"""

import os
import re

from string import ascii_letters

from . import config


def year_file(year):
    """ Returns the database file for a specific year
    This file includes Paper's metadata
    
    Doctest
    >>> from pathlib import Path
    >>> [year_file(2017)]  # doctest: +ELLIPSIS
    [.../work/y2017.py')]
    """
    return config.DATABASE_DIR / 'work' / 'y{}.py'.format(year)


def citation_file(name):
    """ Returns the database file for a specific approach
    This file includes Citation's metadata
    
    Doctest
    >>> from pathlib import Path
    >>> [citation_file('noworkflow2014')]  # doctest: +ELLIPSIS
    [.../citations/noworkflow2014.py')]
    """
    return config.DATABASE_DIR / 'citations' / '{}.py'.format(name)


def places_file():
    """ Returns the places file 
    
    Doctest
    >>> from pathlib import Path
    >>> [places_file()]  # doctest: +ELLIPSIS
    [...places.py')]
    """
    return config.DATABASE_DIR / 'places.py'

def parse_varname(varname, group_index):
    """ Parse the varname convention to extract its parts
    The convention is (last name of first author)(year)(sequential letter)
    The *group_index* argument indicates which part should be extracted
    0 = all the varname
    1 = last name of first author
    2 = year
    3 = sequential letter

    If the varname doesn't match the convention, returns None

    Doctest
    >>> varname = 'murta2014a'
    >>> parse_varname(varname, 0)
    'murta2014a'
    >>> parse_varname(varname, 1)
    'murta'
    >>> parse_varname(varname, 2)
    '2014'
    >>> parse_varname(varname, 3)
    'a'
    >>> varname = 'invalid'
    >>> parse_varname(varname, 0) is None
    True
    """
    return getattr(
        re.search('(.*)(\d\d\d\d)(.*)', varname), 
        'group',
        lambda x: None
    )(group_index)


def this_file(filename):
    """ Extracts filename without python extension
    It is used on citation files in the database to identify them

    Doctest
    >>> this_file(__file__)
    'dbindex'
    """
    return '.'.join(os.path.basename(filename).split('.')[:-1])


def discover_year(varname, year=None, fail_raise=True):
    """ Discovers year from varname or year argument
    If *year* is defined, return it. Otherwise, extracts from *varname*.
    If it fails to extract from varname, it may raise an exception according to *fail_raise*


    Doctest
    >>> discover_year('murta2014a')
    2014
    >>> discover_year('murta2014a', 2015)
    2015
    >>> discover_year('invalid', fail_raise=False) is None
    True
    >>> discover_year('invalid')
    Traceback (most recent call last):
     ...
    ValueError: Year Required
    """
    if year is not None:
        return int(year)
    year = parse_varname(varname, 2)
    if year is None:
        if fail_raise:
            raise ValueError('Year Required')
        return None
    return int(year)


def increment_char(letter):
    """ Increments letter from 'a' through 'z'

    Doctest
    >>> increment_char('a')
    'b'
    >>> increment_char('b')
    'c'
    >>> increment_char('z')
    'a'
    """
    if letter not in ascii_letters:
        return 'a'
    return chr(ord(letter) + 1) if letter != 'z' else 'a'


def increment_str(varname):
    """ Increments letter from varname
    If it reaches the 'z', adds a new 'a' letter and restarts the process
    
    Doctest
    >>> increment_str('murta2014')
    'murta2014a'
    >>> increment_str('murta2014a')
    'murta2014b'
    >>> increment_str('murta2014z')
    'murta2014aa'
    >>> increment_str('murta2014az')
    'murta2014ba'
    """
    lpart = varname.rstrip('z')
    num_replacements = len(varname) - len(lpart)
    new_s = lpart
    if lpart and lpart[-1] in ascii_letters:
        new_s = lpart[:-1] + increment_char(lpart[-1])
    else:
        new_s += "a"
    new_s += 'a' * num_replacements
    return new_s
