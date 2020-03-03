"""This module contains classes for defining the database and producing the
citation graph"""

import inspect
import svgwrite
import operator
import os

from .collection_helpers import oget, oset, dset
from .utils import text_y, adjust_point, Point

from . import dbindex, config


class Title(object):
    """Represent a Title object for svgwrite"""

    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


class WithTitle(object):
    """Graph object with title"""
    ignore = set()

    def generate_title(self, prepend="\n\n"):
        """Generate title text with all attributes from the object

        Ignores attributes that start with `_`, or attributes in the
        :attr:`~ignore` set

        Doctest:

        .. doctest::

            >>> obj = WithTitle()
            >>> obj.attr = 'x'
            >>> obj.attr2 = 'y'
            >>> obj._ignored = 'z'
            >>> print(obj.generate_title(prepend=""))
            attr: x
            attr2: y
            >>> obj.ignore.add('attr')
            >>> print(obj.generate_title(prepend=""))
            attr2: y
        """
        result = "\n".join(
            "{}: {}".format(attr, str(value))
            for attr, value in self.__dict__.items()
            if not attr.startswith("_")
            if not attr in self.ignore
            if value is not None
        )
        return prepend + result if result else ""


class Place(WithTitle):
    """Represent a publication Place

    It has the following attributes:

    * :attr:`~acronym` -- place acronym (e.g., 'IPAW')

      * Surround it with <>, if the place has no acronym or you do not know it
        (e.g., '<ImaginaryAcronym>')

    * :attr:`~name` -- full name of the place (e.g., 'International Provenance
      and Annotation Workshop')

    * :attr:`~type` -- place acronym (e.g., 'IPAW')

    Other attributes are optional and can be used to include extra information
    about the place.
    Note however that it has the following reversed attributes:

    * :attr:`~ignore` -- set that specifies ignore attributes in titles
      (:class:`~WithTitle`)

    * :meth:`~draw` -- method that draws the place


    Doctest:

    .. doctest::

        >>> ipaw = Place('IPAW',
        ...              'International Provenance and Annotation Workshop',
        ...              'conference')
        >>> ipaw.acronym
        'IPAW'
        >>> ipaw.name
        'International Provenance and Annotation Workshop'
        >>> ipaw.type
        'conference'

        Places are considered equal if they have the same name
        >>> ipaw2 = Place('I', 'International Provenance and Annotation Workshop',
        ...              'journal')
        >>> ipaw == ipaw2
        True
    """

    def __init__(self, acronym, name="", *args, **kwargs):
        if name == "":
            name = acronym

        self.acronym = acronym
        self.name = name

        if args:
            self.type = args[0]

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __eq__(self, other):
        if not other:
            return False
        return self.name == other.name

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.acronym

    def __hash__(self):
        return hash(self.name)


class Work(WithTitle):
    """Work represents papers in the snowballing

    It has the following attributes:

    * :attr:`~year` -- year of publivation (int)

      * Convention: use 0 if it is not required (website), or 9999 if it is not
        informed

    * :attr:`~name` -- paper title

    * :attr:`~authors` -- paper authors

      * For exporting properly to BibTeX, I suggest using the format 'LastName1,
        FirstName1 and LastName2, FirstName2 and LastName3, FirstName3 ...'

    * :attr:`~display` -- display label for graphs

    * :attr:`~metakey` -- variable name

      * It is automatically collected from the database. It it does not exist,
        call :func:`snowvalling.operations.reload` again.

    * :attr:`~file` -- filename of the work (optional)

    * :attr:`~due` -- reason for work not being related (optional)

    * :attr:`~notes` -- use it to append a string to year in BibTeX (optional)

      * For example::

            work.year = 2014
            work.notes = "in press"

      * Produces: 2014 [in press]

    * :attr:`~snowball` -- forward snowballing date (optional)

    * :attr:`~citation_file` -- citation filename (without .py)

      * Indicates where are the citations of this work

    * :attr:`~scholar` -- url of the work in google scholar (optional)

    * :attr:`~scholar_ok` -- status of the work according to a google scholar
      curation (optional)

      * True means that we already merged google scholar's bibtex to the work

      * False means that we didn't

    * :attr:`~tracking` indicates if we set an alert for the work (optional)

      * Note: the alert is manual. This tool does not set the alert.
        You can use whatever value you want for it


    Other attributes are optional and can be used to include extra information
    about the work.


    Note however that it has the following reserved attributes:

    * :attr:`~category` -- work status in the snowballing

    * :attr:`~tyear` -- year object for drawing

    * :attr:`~ignore` -- set that specifies ignore attributes in titles
      (:class:`~WithTitle`)

    * :meth:`~draw` -- method that draws the work

    * :attr:`~_x` -- x position for drawing the work

    * :attr:`~_y` -- y position for drawing the work

    * :attr:`~_r` -- radius for circular node drawing

    * :attr:`~_i` -- column index for drawing the work

    * :attr:`~_year_index` -- row index for drawing the work

    * :attr:`~_letters` -- max amount of letters for drawing

    * :attr:`~_shape` -- shape of node (circle vs rectangle)


    Works are considered equal if they have the same place, name and year


    Doctest:

    .. doctest::

        >>> IPAW = Place('IPAW', 'IPAW', 'conference')
        >>> murta2014a = Work(
        ...     2014, "noWorkflow: capturing and analyzing provenance of scripts",
        ...     display="noWorkflow",
        ...     authors="Murta, Leonardo and Braganholo, Vanessa and Chirigati, "
        ...             "Fernando and Koop, David and Freire, Juliana",
        ...     place=IPAW,
        ...     local="Cologne, Germany",
        ...     file="Murta2014a.pdf",
        ...     pp="71--83",
        ...     entrytype="inproceedings",
        ...     citation_file="noworkflow2014",
        ... )
        >>> murta2014a.year
        2014
        >>> murta2014a.name
        'noWorkflow: capturing and analyzing provenance of scripts'
        >>> murta2014a.pp
        '71--83'
    """

    category = "work"
    ignore = {
        "_x", "_y", "_i", "_year_index", "_r", "_letters",
        config.ATTR["name"], config.ATTR["year"]
    }

    def __init__(self, year, name, **kwargs):
        oset(self, "name", name)
        oset(self, "year", year)

        for key, value in kwargs.items():
            setattr(self, key, value)

        self._x = 0
        self._y = 0
        self._i = -1
        self._r = 20
        self._year_index = -1
        self._letters = 5

        config.work_post_init(self)

    def __eq__(self, other):
        return config.work_eq(self, other)

    def __hash__(self):
        return config.work_hash(self)

    def __repr__(self):
        return oget(self, "name")

    def generate_title(self, prepend="\n\n"):
        """The title of a work is its BibTeX"""
        from .operations import work_to_bibtex
        return prepend + work_to_bibtex(self, name=None)

    def draw(self, dwg, fill_color=None, draw_place=False, use_circle=False):
        """Draw work"""
        from .operations import metakey, wdisplay
        position = Point(self._x, self._y)
        if fill_color is None:
            fill_color = lambda x: "white", "black"
        fill, text_fill = fill_color(self)
        
        str_metakey = (self @ metakey) or "work{}".format(id(self))
        if self._shape == "circle":
            shape = svgwrite.shapes.Circle(
                position, self._r, fill=fill, stroke="black",
                id=str_metakey, **{"class":str_metakey}
            )
            shape_text = self._circle_text
        else:
            r2 = Point(self._r, self._r)
            shape = svgwrite.shapes.Rect(
                position - r2, r2 + r2, fill=fill, stroke="black",
                id=str_metakey, **{"class":str_metakey}
            )
            shape_text = self._square_text

        textstr = (self @ wdisplay)[:self._letters]
        text = svgwrite.text.Text(
            "",(self._x, self._y),
            fill=text_fill,
            text_anchor="middle",
            alignment_baseline="middle",
            style="font-size:12px;font-family:monospace",
            class_="wrap"
        )
        for y, line in zip(text_y(len(shape_text)), shape_text):
            #print(y, line)
            text.add(svgwrite.text.TSpan(line, (self._x, self._y + y)))


        shape.set_desc(title=Title(
            config.work_tooltip(self) + self.generate_title()
        ))
        text.set_desc(title=Title(
            config.work_tooltip(self) + self.generate_title()
        ))

        if draw_place:
            place_text = config.graph_place_text(self)
            if place_text:
                self._draw_place(
                    config.graph_place_text(self),
                    config.graph_place_tooltip(self),
                    dwg, position - Point(0, self._r + 4)
                )

        link = config.work_link(self)
        if link is not None:
            link = svgwrite.container.Hyperlink(link)
            dwg.add(link)
            dwg = link

        dwg.add(shape)
        dwg.add(text)

    def _draw_place(self, text, title, dwg, position):
        """ Draws place in a given position """
        text = svgwrite.text.Text(
            text, position,
            text_anchor="middle",
            fill="black"
        )
        text.set_desc(title=Title(title))
        dwg.add(text)


class Site(Work):
    """Represent a site reference

    It does not have an year, but it requires following attributes:

    * :attr:`~name` -- website name

    * :attr:`~link` -- website link

    Doctest:

    .. doctest::

        >>> site = Site("GitHub", "http://www.github.com")
        >>> site.name
        'GitHub'
        >>> site.link
        'http://www.github.com'
    """

    category = "site"

    def __init__(self, name, link, **kwargs):
        from .common_places import Web
        dset(kwargs, "site_link", link)
        super(Site, self).__init__(0, name, place=Web, **kwargs)


class Email(Work):
    """Represent an email reference

    It requires the following attributes:

    * :attr:`~year` -- year it was received

    * :attr:`~authors` -- email author

    * :attr:`~name` -- email subject


    Doctest:

    .. doctest::

        >>> email = Email(2017, "Pimentel, Joao", "noWorkflow model")
        >>> email.year
        2017
        >>> email.authors
        'Pimentel, Joao'
        >>> email.name
        'noWorkflow model'
    """
    category = "site"

    def __init__(self, year, authors, subject, **kwargs):
        from .common_places import Web
        dset(kwargs, "email_authors", authors)
        super(Email, self).__init__(year, subject, place=Web, **kwargs)


class Year(object):
    """Represent a year in the citation graph

    It has the following attributes:

    * :attr:`~year` --  int

    * :attr:`~next_year` --  tuple with year object and index

      * year = -1 indicates that there is no next year

    * :attr:`~previous_year` --  tuple with year object and index
      * previous = -1 indicates that there is no previous year

    * :attr:`~works` --  list of works in the year


    It has the following reversed attributes

    * :attr:`~_i` --  column index for drawing the year

    * :attr:`~_dist` --  distance between year columns

    * :attr:`~_r` -- extra margin


    Doctest:

    .. doctest::

        >>> y2017 = Year(2017, (-1, 0), [])
        >>> y2017.year
        2017
    """

    def __init__(self, year, previous, works, i=-1, dist=60, r=20):
        self.previous_year = previous
        self.next_year = (-1, 0)
        self.works = works
        oset(self, "year", year)
        self._i = i
        self._dist = dist
        self._r = r

    def draw(self, dwg):
        """Draw year in the position"""
        x = self._i * self._dist + self._r
        dwg.add(svgwrite.text.Text(
            oget(self, "year")[0], (x, 20),
            text_anchor="middle",
            style="font-size:20px"
        ))


class Citation(WithTitle):
    """Represent a citation for the work

    Attributes:

    * :attr:`~work` -- the work that cites

    * :attr:`~citation` -- the work that is cited

    Other attributes are optional and can be used to include extra information
    about the citation.


    Note however that it has the following reserved attributes:

    * :attr:`~citations_file` -- file where the citation is defined
    """
    ignore = {"work", "citation"}

    def __init__(self, work, citation, **kwargs):
        import inspect
        import os

        self._citations_file = dbindex.last_citation_file

        self.work = work
        self.citation = citation

        for key, value in kwargs.items():
            setattr(self, key, value)

    def _belzier_gen(self, work, ref, rotate):
        """Create belzier line points
        Usage:
        ... svgwrite.path.Path(
        ...      "M{0} C{1} {2} {3}".format(*belzier_gen(work, ref, False)
        ...  ), stroke="black", fill="white", fill_opacity=0)
        """
        work_point = Point(work._x, work._y)
        ref_point = Point(ref._x, ref._y)
        yield work_point + Point(-work._r, 0).rotate(rotate)
        yield work_point + Point(-2 * work._r, 0).rotate(rotate)
        yield ref_point + Point(-2 * ref._r, 0).rotate(rotate)
        yield ref_point + Point(-ref._r - 7, 0).rotate(rotate)

    def _line_gen(self, work, ref):
        """Create line points

        Usage::

            svgwrite.shapes.Line(*self._line_gen(work, ref), stroke="black")
        """
        point0 = adjust_point(
            ref._x, ref._y, work._x, work._y, work._r, work._shape
        )
        yield point0
        yield adjust_point(*point0, ref._x, ref._y, ref._r + 7, ref._shape)

    def draw(self, dwg, marker, years, rows, draw_place=False):
        """Draw citation line"""
        from .operations import metakey
        work, ref = self.work, self.citation
        if work == ref:
            return
        if not hasattr(work, "tyear") or not hasattr(ref, "tyear"):
            return
        if work.tyear not in years or ref.tyear not in years:
            return
        if work._i not in rows or ref._i not in rows:
            return
        group = dwg.g(class_="hoverable")
        if abs(ref._x - work._x) <= work._dist_x and abs(ref._y - work._y) <= work._dist_y:
            sign = 1 if work._x < ref._x else -1
            line = svgwrite.shapes.Line(*self._line_gen(work, ref), stroke_opacity=0.3, stroke="black")
            line["marker-end"] = marker.get_funciri()
            line.set_desc(title=Title(
                "{0} -> {1}".format(work @ metakey, ref @ metakey)
                + self.generate_title()
            ))
            group.add(line)
        else:
            space_x = work._dist_x - 2 * work._r
            space_y = work._dist_y - 2 * work._r
            if draw_place:
                space_y -= 16
            work_year = years[work.tyear]
            ref_year = years[ref.tyear]
            if work._x < ref._x:
                closest_work_year = years[work_year.next_year]
                closest_ref_year = years[ref_year.previous_year]
                pS, pE = Point(work._r, 0), Point(-(ref._r + 7), 0)
                pSM, pEM = Point(0, 0), Point(-space_x + 7, 0)
                signx = -1
            else:
                closest_work_year = years[work_year.previous_year]
                closest_ref_year = years[ref_year.next_year]
                pS, pE = Point(-work._r, 0), Point((ref._r + 7), 0)
                pSM, pEM = Point(-space_x, 0), Point(0, 0)
                signx = 1
            total_work = len(work_year.works) + len(closest_work_year.works)
            total_ref = len(ref_year.works) + len(closest_ref_year.works)

            delta_work = (space_x - 7) / float(total_work + 1)
            delta_ref_x = (space_y - 7) / float(total_ref + 1)
            dist_midwork = 7 + delta_work * (work._i + 1)
            dist_midref_x = 7 + len(closest_ref_year.works) + delta_ref_x * (ref._i + 1)

            total_ref_y = len(rows[ref._i])
            delta_ref_y = (space_y - 7) / float(total_ref_y + 1)
            dist_midref_y = delta_ref_y * ((len(rows[ref._i]) - ref._year_index))

            signy = 1 if work._y < ref._y else -1
            source_points = [Point(work._x, work._y) + pS]
            source_points.append(source_points[0] + pSM + Point(dist_midwork, 0))
            if work._x != ref._x:
                position_in_row = rows[ref._i].index(ref)
                next_position = position_in_row + signx
                operation = [0, operator.ge, operator.le][signx]
                if next_position in (-1, len(rows[ref._i])) or operation(rows[ref._i][next_position].tyear, work.tyear):
                    target_points = [Point(ref._x, ref._y) + pE]
                else:
                    target_points = [Point(ref._x, ref._y) + Point(0, ref._r + 7)]
                    target_points.append(target_points[0] + Point(0, dist_midref_y))
            else:
                target_points = [Point(ref._x, ref._y) + Point(-(ref._r + 7), 0)]
            target_points.append(Point(source_points[-1].x, target_points[-1].y))

            points = source_points + list(reversed(target_points))
            line = svgwrite.shapes.Polyline(points, stroke_opacity=0.3, stroke="black", fill="none", pointer_events="stroke")
            line.set_desc(title=Title("{0} -> {1}".format(work @ metakey, ref @ metakey) + self.generate_title()))
            group.add(line)

            line["marker-end"] = marker.get_funciri()
        dwg.add(group)


class Database(object):
    """Represent a database with all elements that can be accessed"""

    def __init__(self):
        self._elements = []

    def filter(self, type):
        """Filter database by type"""
        for k, v in self.__dict__.items():
            if not k.startswith("_") and isinstance(v, type):
                yield v

        for v in self._elements:
            if isinstance(v, type):
                yield v

    def clear(self, type):
        """Clear type from database"""
        for k, v in self.__dict__.items():
            if not k.startswith("_") and isinstance(v, type):
                delattr(self, k)

        self._elements = [v for v in self._elements if not isinstance(v, type)]

    def clear_work(self):
        """Clear all work"""
        self.clear(Work)

    def clear_places(self):
        """Clear all places"""
        self.clear(Place)

    def clear_citations(self):
        """Clear citations"""
        self.clear(Citation)

    def work(self):
        """Generate all work"""
        yield from self.filter(Work)

    def places(self):
        """Generate all places"""
        yield from self.filter(Place)

    def citations(self):
        """Gerenete all citations"""
        yield from self.filter(Citation)

    def __call__(self, *args, **kwargs):
        if args:
            element = args[0]
            self._elements.append(element)
            return element
        elif kwargs:
            for k, v in kwargs.items():
                setattr(self, k, v)
                return v


for (cls_name, category, *_) in config.CLASSES:
    if cls_name not in locals():
        attrs = {}
        dset(attrs, "category", category)
        locals()[cls_name] = type(cls_name, (Work,), attrs)
    else:
        oset(locals()[cls_name], "category", category)

DB = Database()
