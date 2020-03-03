"""This module contains helpers for configuring the project"""

import re

from string import ascii_lowercase

from .collection_helpers import consume_key
from .utils import compare_str, match_any


def last_name_first_author(authors):
    """Return displays of info based on the authors field

    Selects the last name of the first author

    Doctest:

    .. doctest::
        >>> last_name_first_author('Pimentel, Joao')
        'pimentel'
        >>> last_name_first_author('Pimentel, Joao and Braganholo, Vanessa')
        'pimentel'
        >>> last_name_first_author('Joao Pimentel')
        'pimentel'
        >>> last_name_first_author('Joao Pimentel and Vanessa Braganholo')
        'pimentel'
        >>> last_name_first_author('Joao Pimentel, Vanessa Braganholo')
        'pimentel'
    """
    if " and " in authors:
        authors = authors.split(" and ")[0]
    if "," not in authors:
        last = authors.split()[-1]
    else:
        last = re.findall(r'(\w*)[`\-=~!@#$%^&*()_+\[\]{};\'\\:"|<,/<>?]', authors)[0]
    return last.lower()


def reorder_place(place):
    """Reorder common place patterns and remove numbers
    
    Patterns:

    * Proceedings of the
    * International Conference on
    * International Convention on
    * International Symposium on

    """
    place = place.replace("Proceedings of the ", "")
    place = re.sub(r"(?<=[0-9])(?:st|nd|rd|th)", "", place)
    place = re.sub(r"(.*) (International Conference on)", r"\2 \1", place, flags=re.I)
    place = re.sub(r"(.*) (International Convention on)", r"\2 \1", place, flags=re.I)
    place = re.sub(r"(.*) (International Symposium on)", r"\2 \1", place, flags=re.I)
    return "".join([i for i in place if not i.isdigit()])


def select_param(obj, old, new, current):
    return {
        "old": old,
        "new": new,
        "current": current,
    }[obj]


def var_item(key, before="", after=",", obj="old", use_key=True):
    def var_item_apply(old, new, current):
        value = select_param(obj, old, new, current).get(key)
        if value:
            consume_key(current, key, use_key)
            func = str if isinstance(value, str) else repr
            return "{}{}={}{}".format(
                before, key, func(value), after
            )
        return ""
    return var_item_apply


def str_list(key, before="", after=",", obj="old", use_key=True):
    def str_list_apply(old, new, current):
        value = select_param(obj, old, new, current).get(key)
        if value:
            consume_key(current, key, use_key)
            return "{}{}=[{}]{}".format(
                before, key, ", ".join('"{}"'.format(e) for e in value.split(",")), after
            )
        return ""
    return str_list_apply


def str_item(key, before="", after=",", obj="old", use_key=True):
    def str_item_apply(old, new, current):
        value = select_param(obj, old, new, current).get(key)
        if value:
            consume_key(current, key, use_key)
            return '{}{}="{}"{}'.format(
                before, key, value, after
            )
        return ""
    return str_item_apply


def sequence(funcs, default=""):
    def new_func(old, new, current):
        for func in funcs:
            result = func(old, new, current)
            if result:
                return result
        return default
    return new_func


def work_by_varname(varname):
    from .operations import work_by_varname
    return work_by_varname(varname)


def find_work_by_info(paper, pyrefs=None):
    from .operations import find_work_by_info
    return find_work_by_info(paper, pyrefs=None)


def Site(*args):
    from .models import Site
    return Site(*args)


def set_config(tag, name=None):
    def dec(func):
        from . import config
        config_func = getattr(config, name or func.__name__)
        if not hasattr(config_func, "tags"):
            config_func.tags = set()
        if tag not in config_func.tags:
            if not hasattr(func, "tags"):
                func.tags = set()
            func.tags.add(tag)
            setattr(config, func.__name__, func)
            return func
        return config_func
    return dec


def generate_title(obj, prepend="\n\n", ignore={"_.*"}):
    """Generate title text with all attributes from the object

    Ignores attributes that start with `_`, or attributes in the
    :attr:`~ignore` set

    Doctest:

    .. doctest::
        >>> class A: pass
        >>> obj = A()
        >>> obj.attr = 'x'
        >>> obj.attr2 = 'y'
        >>> obj._ignored = 'z'
        >>> print(generate_title(obj, prepend=""))
        attr: x
        attr2: y
        >>> print(generate_title(obj, prepend="", ignore={"_.*", "attr"}))
        attr2: y
    """
    result = "\n".join(
        "{}: {}".format(attr, str(value))
        for attr, value in obj.__dict__.items()
        if not match_any(attr, ignore)
        if value is not None
    )
    return prepend + result if result else ""
