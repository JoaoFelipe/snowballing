"""This module produces citation graphs"""

import svgwrite

from collections import OrderedDict, defaultdict
from itertools import groupby
from pathlib import Path

from ipywidgets import Text, ToggleButton, IntSlider, VBox, HBox, Box, Button, Output
from ipywidgets import ColorPicker

from IPython.display import SVG, clear_output
from IPython.display import display, Javascript, HTML

from .collection_helpers import oget
from .models import Year
from .operations import load_work, load_citations, reload, wdisplay
from .utils import lines_len_in_circle, multiline_wrap

from . import config


class GraphConfig:
    """Configure graph"""
    def __init__(self, **kwargs):
        self._max_by_year = float('inf')
        self.r = 20
        self.margin = 70
        self.margin_left = 20
        self.dist_x = 60
        self.dist_y = 60
        self.letters = 5
        self.shape = "square"
        self.max_by_year = 5
        self.fill_color = None
        self.draw_place = False

        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def max_by_year(self):
        return self._max_by_year

    @max_by_year.setter
    def max_by_year(self, value):
        self._max_by_year = value
        if value <= 0:
            self._max_by_year = float('inf')


def set_positions(work_list, graph_config=None):
    """Set positions for each work

    Arguments:

    * `work_list` -- list of work

    Keyword arguments:

    * `graph_config` -- GraphConfig object with style configurations
    """
    graph_config = graph_config or GraphConfig()
    by_year = defaultdict(list)
    years = {}
    rows = defaultdict(list)
    lines_len = lines_len_in_circle(graph_config.r)
    for year, works in groupby(work_list, lambda x: oget(x, "year")):
        tyear = (year, 0)
        for work in works:
            while len(by_year[tyear]) >= graph_config.max_by_year:
                tyear = (year, tyear[1] + 1)
            i = (len(by_year[tyear]))
            work._y = graph_config.margin + graph_config.dist_y * i
            work._i = i
            work._r = graph_config.r
            work._dist_x = graph_config.dist_x
            work._dist_y = graph_config.dist_y
            work._margin = graph_config.margin
            work._letters = graph_config.letters
            work._circle_text = multiline_wrap(work @ wdisplay, lines_len)
            work._square_text = multiline_wrap(
                work @ wdisplay, [graph_config.letters] * len(lines_len)
            )
            work._shape = graph_config.shape
            work._link = ["scholar", "link"]#["file", "link", "scholar"]
            work.tyear = tyear
            by_year[tyear].append(work)

    prev = (-1, 0)
    years[prev] = Year(
        prev, prev, [], dist=graph_config.dist_x, r=graph_config.margin_left
    )
    max_in_one_year = -1
    for i, tyear in enumerate(sorted(by_year.keys())):
        years[prev].next_year = tyear
        for work in by_year[tyear]:
            work._x = graph_config.dist_x * i + graph_config.margin_left
            work._year_index = len(rows[work._i])
            rows[work._i].append(work)
        years[tyear] = Year(
            tyear, prev, by_year[tyear], i,
            dist=graph_config.dist_x, r=graph_config.margin_left
        )
        prev = tyear
        max_in_one_year = max(max_in_one_year, len(by_year[tyear]))

    return years, rows, max_in_one_year


def create_graph(name, work_list, references, graph_config=None):
    """Create citation graph

    Arguments:

    * `name` -- file name
    * `work_list` -- list of work
    * `references` -- list of citations

    Keyword arguments:

    * `graph_config` -- GraphConfig object with style configurations
    """
    graph_config = graph_config or GraphConfig()
    years, rows, max_in_one_year = set_positions(work_list, graph_config)

    dwg = svgwrite.Drawing(name, size=(
        (len(years) - 2) * graph_config.dist_x + 2 * graph_config.margin_left,
        2 * graph_config.margin + (max_in_one_year - 1) * graph_config.dist_y
    ))

    marker = svgwrite.container.Marker(
        markerWidth="7", markerHeight="10", orient="auto", refY="5"
    )
    marker.add(svgwrite.path.Path(
        "M0,10 L7,5 0,0", fill="black", stroke="black"
    ))
    dwg.defs.add(marker)


    for work in work_list:
        work.draw(
            dwg,
            fill_color=graph_config.fill_color,
            draw_place=graph_config.draw_place
        )

    for ref in references:
        ref.draw(dwg, marker, years, rows, draw_place=graph_config.draw_place)

    tyear = years[(-1, 0)].next_year
    while tyear != (-1, 0):
        years[tyear].draw(dwg)
        tyear = years[tyear].next_year

    from xml.etree.ElementTree import tostring
    dwg.tostring = lambda self=dwg: tostring(self.get_xml()).decode("utf-8")
    dwg.save()
    return dwg


class Graph(VBox):
    """Graph widget class for creating interactive graphs

    Keyword arguments:

    * `name` -- graph name
    * `delayed` -- use a draw button instead of updating on every change
    * `**kwargs` -- default configurations for the graph according to
      GraphConfig attributes and category names
    """

    def __init__(self, name="graph", delayed=False, **kwargs):
        self._display_stack = 1
        self._display_categories = set()
        self._filter_in = None
        self._filter_out = None
        self._svg_name = ""
        self._initial = kwargs
        self.delayed = delayed

        self.graph_name = name
        self.toggle_widgets = OrderedDict()
        self.color_widgets = OrderedDict()
        self.font_color_widgets = OrderedDict()

        self.filter_in_widget = Text(description="Filter In", value=kwargs.get("filter_in", ""))
        self.filter_out_widget = Text(description="Filter Out", value=kwargs.get("filter_out", ""))

        self.r_widget = self.slider("R", "r", 5, 70, 1, 21, fn=self.update_r_widget)
        self.margin_widget = self.slider("Margin", "margin", 5, 170, 1, 59)
        self.margin_left_widget = self.slider("M. Left", "margin_left", 5, 170, 1, 21)
        self.dist_x_widget = self.slider("Dist. X", "dist_x", 5, 170, 1, 76)
        self.dist_y_widget = self.slider("Dist. Y", "dist_y", 5, 170, 1, 76)
        self.letters_widget = self.slider("Letters", "letters", 1, 40, 1, 7)
        self.by_year_widget = self.slider("By Year", "max_by_year", 0, 50, 1, 5)

        self.places_widget = ToggleButton(description="Places",
                                          value=kwargs.get("places", False))
        self.references_widget = ToggleButton(description="References",
                                              value=kwargs.get("references", True))
        self.delayed_widget = Button(description="Draw")

        self.output_widget = Output()


        self.filter_in_widget.observe(self.update_widget, "value")
        self.filter_out_widget.observe(self.update_widget, "value")
        self.places_widget.observe(self.update_widget, "value")
        self.references_widget.observe(self.update_widget, "value")
        self.delayed_widget.on_click(self.delayed_draw)

        self.create_widgets()

        self.update_r_widget()

        super(Graph, self).__init__([
            HBox([
                VBox(
                    [
                        self.filter_in_widget, self.filter_out_widget
                    ] +
                    list(self.toggle_widgets.values()) +
                    [
                        HBox([w1, w2])
                        for w1, w2 in zip(self.color_widgets.values(), self.font_color_widgets.values())
                    ] +
                    [
                        self.places_widget, self.references_widget
                    ] +
                    ([self.delayed_widget] if delayed else [])
                ),
                VBox([
                    self.r_widget, self.margin_widget, self.margin_left_widget,
                    self.dist_x_widget, self.dist_y_widget,
                    self.letters_widget, self.by_year_widget,
                ]),
            ]),
            self.output_widget
        ])
        self.layout.display = 'flex'
        self.layout.align_items = 'stretch'
        self.delayed_draw()

    def delayed_draw(self, *args):
        """Draw graph"""
        self._display_stack = 0
        self.display()

    def slider(self, description, attribute, min, max, step, default, fn=None):
        """Creates slider"""
        widget = IntSlider(
            description=description,
            min=min,
            max=max,
            step=step,
            value=self._initial.get(attribute, default),
        )
        widget._configattr = attribute
        widget.observe(fn or self.update_widget, "value")
        return widget

    def update_widget(self, *args):
        """Callback for generic widgets"""
        self._display_stack += 1
        self.display()

    def update_r_widget(self, *args):
        """Callback for updating r_widget value"""
        self._display_stack += 1
        r_value = self.r_widget.value
        dist_min = 2 * r_value + 2
        letters_max = int(r_value / 3.6)
        self.margin_left_widget.min = -1
        self.margin_left_widget.value = max(r_value, self.margin_left_widget.value)
        self.margin_left_widget.min = r_value
        self.dist_x_widget.min = -1
        self.dist_x_widget.value = max(dist_min, self.dist_x_widget.value)
        self.dist_x_widget.min = dist_min
        self.dist_y_widget.min = -1
        self.dist_y_widget.value = max(dist_min, self.dist_y_widget.value)
        self.dist_y_widget.min = dist_min
        self.letters_widget.max = 5000
        self.letters_widget.value = min(letters_max, self.letters_widget.value)
        self.letters_widget.max = letters_max
        self.display()

    def visible_classes(self):
        """Generate classes"""
        for class_ in config.CLASSES:
            if class_[2] in ("display", "hide"):
                yield class_

    def create_category(self, name, attr, value, color, font_color):
        """Create category widget"""
        VIS = ['none', '']
        widget = self.toggle_widgets[attr] = ToggleButton(value=value, description=name)
        wcolor = self.color_widgets[attr] = ColorPicker(value=color, description=name, width="180px")
        wfont_color = self.font_color_widgets[attr] = ColorPicker(value=font_color, width="110px")
        def visibility(*args):
            """" Toggles visibility of category """
            self._display_stack += 1
            wcolor.layout.display = VIS[int(widget.value)]
            wfont_color.layout.display = VIS[int(widget.value)]
            self.display()
        widget.observe(visibility, "value")
        wcolor.observe(self.update_widget, "value")
        wfont_color.observe(self.update_widget, "value")
        visibility()

    def create_widgets(self):
        """Create custom categories"""
        for class_ in self.visible_classes():
            self.create_category(
                class_[0], class_[1],
                (class_[2] == "display"),
                class_[3], class_[4],
            )

    def graph(self):
        """Create graph"""
        reload()
        work_list = load_work()
        references = load_citations()

        self._svg_name = str(Path("output") / (self.graph_name + ".svg"))
        self._display_categories = {
            key for key, widget in self.toggle_widgets.items()
            if widget.value
        }
        self._filter_in = self.filter_in_widget.value.lower()
        self._filter_out = self.filter_out_widget.value.lower()

        work_list = list(filter(self.filter_work, work_list))
        ref_list = []
        if self.references_widget.value:
            references = ref_list = list(filter(
                lambda x: self.filter_work(x.citation) and self.filter_work(x.work),
                references
            ))

        graph_config = GraphConfig()
        graph_config.r = self.r_widget.value
        graph_config.margin = self.margin_widget.value
        graph_config.margin_left = self.margin_left_widget.value
        graph_config.dist_x = self.dist_x_widget.value
        graph_config.dist_y = self.dist_y_widget.value
        graph_config.letters = self.letters_widget.value
        graph_config.max_by_year = self.by_year_widget.value
        graph_config.draw_place = self.places_widget.value
        graph_config.fill_color = self.work_colors

        create_graph(self._svg_name, work_list, ref_list, graph_config)
        return work_list, ref_list

    def work_key(self, work):
        """Return work category"""
        return oget(work, "category")

    def work_colors(self, work):
        """Return colors for work"""
        key = self.work_key(work)
        if key not in self.color_widgets:
            return ('white', 'black')
        return (
            self.color_widgets[key].value,
            self.font_color_widgets[key].value
        )

    def filter_work(self, work):
        """Filter work"""
        key = self.work_key(work)
        if key not in self._display_categories:
            return False
        for attr in dir(work):
            if self._filter_out and self._filter_out in str(getattr(work, attr)).lower():
                return False
        for attr in dir(work):
            if self._filter_in in str(getattr(work, attr)).lower():
                return True
        return False

    def display(self, *args):
        """Display interactive graph"""
        if self._display_stack:
            if not self.delayed:
                self._display_stack -= 1
            if self._display_stack:
                # Skip display if other widgets will invoke display soon
                return False
        self.output_widget.clear_output()
        with self.output_widget:
            work_list, references = self.graph()
            display(self._svg_name)
            svg = SVG(self._svg_name)
            svg._data = svg._data[:4] + ' class="refgraph"' + svg._data[4:]
            display(svg)

            interaction = """
                $(".hoverable polyline, .hoverable line").mouseenter(
                    function(e) {
                        //e.stopPropagation();
                        $(this).css("stroke", "blue");
                        $(this).css("stroke-width", "3px");
                    }).mouseleave(
                    function() {
                        $(this).css("stroke", "black");
                        $(this).css("stroke-width", "inherit");
                    });
            """
            display(Javascript(interaction))
            display(HTML("""
                <script type="text/javascript">
                    %s

                    require(["./svg-pan-zoom"], function(svgPanZoom) {
                        svgPanZoom('.refgraph', {'minZoom': 0.1});
                    });
                </script>
            """ % (
                open(
                    Path(__file__) / ".." / ".." /
                    "resources" / "svg-pan-zoom.min.js"
                ).read(),
            )))

        return True


def getcolors():
    """Generate colors"""
    kelly_colors = OrderedDict([
        ('D6.1', (137, 80, 10)),
        ('D6.2', (216, 179, 101)),
        ('D6.4', (199, 234, 229)),
        ('D6.5', (90, 180, 172)),
        ('D6.6', (1, 41, 37)),
        ('D6.3', (246, 232, 195)),

        ('vivid_yellow', (255, 179, 0)),
        ('strong_purple', (128, 62, 117)),
        ('vivid_orange', (255, 104, 0)),
        ('very_light_blue', (166, 189, 215)),
        ('vivid_red', (193, 0, 32)),
        ('grayish_yellow', (206, 162, 98)),
        ('medium_gray', (129, 112, 102)),

        # these aren't good for people with defective color vision:
        ('vivid_green', (0, 125, 52)),
        ('strong_purplish_pink', (246, 118, 142)),
        ('strong_blue', (0, 83, 138)),
        ('strong_yellowish_pink', (255, 122, 92)),
        ('strong_violet', (83, 55, 122)),
        ('vivid_orange_yellow', (255, 142, 0)),
        ('strong_purplish_red', (179, 40, 81)),
        ('vivid_greenish_yellow', (244, 200, 0)),
        ('strong_reddish_brown', (127, 24, 13)),
        ('vivid_yellowish_green', (147, 170, 0)),
        ('deep_yellowish_brown', (89, 51, 21)),
        ('vivid_reddish_orange', (241, 58, 19)),
        ('dark_olive_green', (35, 44, 22))])
    while True:
        for color in kelly_colors.values():
            yield color
        print("WARNING: repeating colors")


def getsvgcolors():
    """Generate pairs of colors"""
    textcolors = OrderedDict([
        ((140, 81, 10), "white"),
        ((216, 179, 101), "black"),
        ((199, 234, 229), "black"),
        ((90, 180, 172), "white"),
        ((1, 102, 94), "white"),
        ((246, 232, 195), "black"),
    ])

    for color in getcolors():
        yield (
            "#{:02X}{:02X}{:02X}".format(*color),
            textcolors.get(color, "white")
        )
