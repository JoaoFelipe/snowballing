"""This module contains helper utility functions"""
import re
import importlib
import pkgutil
import difflib
import sys

from collections import namedtuple
from textwrap import TextWrapper
from math import asinh, asin, cos
from math import atan2, sin


import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from IPython.display import display



def parse_bibtex(bib):
    """Parse BibTex and return list of entries"""
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    return bibtexparser.loads(bib, parser=parser).entries


def text_y(lines, font_size=12):
    """Return a list of lines positions according to how many lines are available

    Doctest:

    .. doctest::

        >>> text_y(0)
        [0]
        >>> text_y(1)
        [0]
        >>> text_y(2)
        [-6, 6]
        >>> text_y(3)
        [-12, 0, 12]
        >>> text_y(4)
        [-18, -6, 6, 18]
        >>> text_y(5)
        [-24, -12, 0, 12, 24]
        >>> text_y(6)
        [-30, -18, -6, 6, 18, 30]
        >>> text_y(7)
        [-36, -24, -12, 0, 12, 24, 36]
    """
    if lines < 2:
        return [0]
    extra = (lines // 2 - 1) * font_size
    final = font_size + extra
    if lines % 2 == 0:
        final = font_size // 2 + extra
    return list(range(-final, final + 1, font_size))


def lines_len_in_circle(r, font_size=12, letter_width=7.2):
    """Return the amount of chars that fits each line in a circle according to
    its radius *r*

    Doctest:

    .. doctest::

        >>> lines_len_in_circle(20)
        [2, 5, 2]
    """
    lines = 2 * r // font_size
    positions = [
        x + (font_size // 2) * (-1 if x <= 0 else 1)
        for x in text_y(lines)
    ]
    return [
        int(2 * r * cos(asin(y / r)) / letter_width)
        for y in positions
    ]


def multiline_wrap(text, widths=[10]*5):
    """Wrap text in multiple lines according to pre-specified widths

    Doctest:
    
    .. doctest::
    
        >>> multiline_wrap('ab cd ef gh', widths=[5, 2, 2])
        ['ab cd', 'ef', 'gh']
    """
    from copy import copy
    max_wrap = []
    for i in range(len(widths)):
        current_widths = []
        widths2 = copy(widths)
        for j in range(i + 1):
            k = max(
                (i for i, v in enumerate(widths2)),
                key=lambda x: widths2[x]
            )
            current_widths.append((k + j - 1, widths2.pop(k)))
        ws = [x for i, x in sorted(current_widths)]
        w = MultiLine(ws)
        w.placeholder = "…"
        current_wrap = w.wrap(text)
        max_wrap = max(
            [max_wrap, current_wrap],
            key=lambda x: sum(len(s) - 0.1 for s in x)
        )
    return max_wrap


class MultiLine(TextWrapper):
    """MultiLine wrapper that considers different widths for each line"""

    def __init__(self, widths, **kwargs):
        super(MultiLine, self).__init__(width=widths[0], **kwargs)
        self.widths = widths
        self.max_lines = len(widths)

    def _wrap_chunks(self, chunks):
        """_wrap_chunks(chunks : [string]) -> [string]

        Wrap a sequence of text chunks and return a list of lines of
        length 'self.width' or less.  (If 'break_long_words' is false,
        some lines may be longer than this.)  Chunks correspond roughly
        to words and the whitespace between them: each chunk is
        indivisible (modulo 'break_long_words'), but a line break can
        come between any two chunks.  Chunks should not have internal
        whitespace; ie. a chunk is either all whitespace or a "word".
        Whitespace chunks will be removed from the beginning and end of
        lines, but apart from that whitespace is preserved.
        """
        lines = []
        if self.width <= 0:
            raise ValueError("invalid width %r (must be > 0)" % self.width)
        if self.max_lines is not None:
            if self.max_lines > 1:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent
            if len(indent) + len(self.placeholder.lstrip()) > self.width:
                raise ValueError("placeholder too large for max width")

        # Arrange in reverse order so items can be efficiently popped
        # from a stack of chucks.
        chunks.reverse()

        while chunks:

            # Start the list of chunks that will make up the current line.
            # cur_len is just the length of all the chunks in cur_line.
            cur_line = []
            cur_len = 0

            # Figure out which static string will prefix this line.
            if lines:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent

            # Maximum width for this line.
            self.width = self.widths[len(lines)]
            width = self.width - len(indent)

            # First chunk on line is whitespace -- drop it, unless this
            # is the very beginning of the text (ie. no lines started yet).
            if self.drop_whitespace and chunks[-1].strip() == "" and lines:
                del chunks[-1]

            while chunks:
                l = len(chunks[-1])

                # Can at least squeeze this chunk onto the current line.
                if cur_len + l <= width:
                    cur_line.append(chunks.pop())
                    cur_len += l

                # Nope, this line is full.
                else:
                    break

            # The current line is full, and the next chunk is too big to
            # fit on *any* line (not just this one).
            if chunks and len(chunks[-1]) > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
                cur_len = sum(map(len, cur_line))

            # If the last chunk on this line is all whitespace, drop it.
            if self.drop_whitespace and cur_line and cur_line[-1].strip() == "":
                cur_len -= len(cur_line[-1])
                del cur_line[-1]

            if cur_line:
                if (self.max_lines is None or
                    len(lines) + 1 < self.max_lines or
                    (not chunks or
                     self.drop_whitespace and
                     len(chunks) == 1 and
                     not chunks[0].strip()) and cur_len <= width):
                    # Convert current line back to a string and store it in
                    # list of all lines (return value).
                    lines.append(indent + "".join(cur_line).replace("  ", ""))
                else:
                    while cur_line:
                        if (cur_line[-1].strip() and
                            cur_len + len(self.placeholder) <= width):
                            cur_line.append(self.placeholder)
                            lines.append(indent + "".join(cur_line).replace("  ", ""))
                            break
                        cur_len -= len(cur_line[-1])
                        del cur_line[-1]
                    else:
                        if lines:
                            prev_line = lines[-1].rstrip()
                            if (len(prev_line) + len(self.placeholder) <=
                                    self.widths[len(lines) - 1]):
                                lines[-1] = prev_line + self.placeholder
                                break
                        lines.append(indent + self.placeholder.lstrip())
                    break

        return lines


class Point(namedtuple("Point", "x y")):
    """Represent a point with two coordinates with operations

    Doctest:

    .. doctest::

        >>> point = Point(3, 4)
        >>> point.x
        3
        >>> point.y
        4
        >>> point[0]
        3
        >>> point[1]
        4
    """
    
    def __str__(self):
        """Represent a point
        
        Doctest:

        .. doctest:

            >>> str(Point(3, 4))
            '3,4'
        """
        return ",".join(map(str, self))
    
    def __add__(self, other):
        """Add points

        Doctest:

        .. doctest:

            >>> Point(1, 2) + Point(3, 4)
            Point(x=4, y=6)
        """
        return Point(self.x + other[0], self.y + other[1])

    def __sub__(self, other):
        """Subtract points

        Doctest:

        .. doctest:

            >>> Point(1, 2) - Point(3, 4)
            Point(x=-2, y=-2)
        """
        return self + Point(-other.x, -other.y)
    
    def rotate(self, should_rotate=True):
        """Swap coordinates

        Doctest:

        .. doctest::

            >>> Point(1, 2).rotate()
            Point(x=2, y=1)
        """
        if should_rotate:
            return Point(self.y, self.x)
        return self


def adjust_point(x0, y0, x1, y1, dt, shape="circle"):
    """Calculate the point in (x1, y1) that should be connected to (x0, y0) 
    according to the radius (or distance to center) *dt*

    Doctest:

    .. doctest::

        >>> adjust_point(0, 0, 0, 10, 5)
        (0, 5)
        >>> adjust_point(0, 0, 10, 0, 5)
        (5, 0)
    """
    sign_x = 1 if x1 > x0 else -1
    sign_y = 1 if y1 > y0 else -1
    if y0 == y1:
        return (x1 - dt * sign_x, y0)
    if (x0 == x1):
        return (x0, y1 - dt * sign_y)
    if shape == "circle":
        dy = y1 - y0
        dx = x1 - x0
        arc = atan2(dy, dx)
        dist = dy / sin(arc)
        dy = (dist - dt) * sin(arc)
        dx = (dist - dt) * cos(arc)
        return (x0 + dx, y0 + dy)
    return (x1 - dt * sign_x, y1 - dt * sign_y)


def import_or_reload(full_name):
    if full_name in sys.modules:
        importlib.reload(sys.modules[full_name])
        return sys.modules[full_name]
    module = importlib.import_module(full_name)
    return module


def import_submodules(package, recursive=True):
    """Import all submodules of a module, recursively, including subpackages

    Arguments:

    * `package` -- package (name or actual module)

    Keyword arguments:

    * `recursive` -- import modules recursively
    """
    if package is None:
        return {}
    if isinstance(package, str):
        package = import_or_reload(package)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name

        results[full_name] = import_or_reload(full_name)
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results


def compare_str(first, second):
    """Compare strings and return matching ratio

    Doctest:

    .. doctest::

        >>> compare_str('abcd', 'abed')
        0.75
    """
    return difflib.SequenceMatcher(None, first, second).ratio()


def match_any(string, regexes):
    """Check if string matches any regex in list

    Doctest:

    .. doctest::

        >>> match_any("a", ["b", "c"])
        False
        >>> match_any("a", ["b", "c", "a"])
        True
        >>> match_any("_a", ["b", "c", "a"])
        False
        >>> match_any("_a", ["b", "c", "a", "_.*"])
        True
    """
    if len(regexes) >= 100:
        return any(re.match(regex + "$", string) for regex in regexes)
    else:
        combined = "({})".format(")|(".join(regex + "$" for regex in regexes))
        return bool(re.match(combined, string))
    

def display_list(elements):
    """Display list of elements using IPython display"""
    for disp in elements or []:
        display(disp)
