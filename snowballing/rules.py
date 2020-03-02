import warnings

from copy import copy, deepcopy
from itertools import zip_longest

from .collection_helpers import callable_get, setitem, consume
from .utils import match_any


class ConvertDict(object):
    """Convert dict into another according to rules"""

    def __init__(self, rules):
        self.rules = rules

    def has(self, original, key):
        return key in original

    def get(self, original, key):
        return original[key]

    def attrs(self, original):
        return original.keys()

    def iterate_remaining(self, original, current):
        return current.items()

    def indicate_usage(self, current, key):
        consume(current, key)

    def new_current(self, original):
        return copy(original)

    def process_element(self, command, new, original, current):
        if isinstance(command, str):
            return command
        if callable(command):
            if command.__code__.co_argcount == 1:
                return command(original)
            if command.__code__.co_argcount == 2:
                return command(original, new)
            return command(original, new, current)

    def apply(self, new, original, current, commands, key=None):
        for command in commands:
            if isinstance(command, (tuple, list)):
                # Command is a tuple with (key, value)
                # Previous values do not matter
                new_key = self.process_element(command[0], new, original, current)
                new_value = self.process_element(command[1], new, original, current)
                if new_key is not None and new_value is not None:
                    new[new_key] = new_value
            elif self.has(original, key):
                # Command is a new key.
                # It uses the previous key to get the value
                new_key = self.process_element(command, new, original, current)
                if new_key is not None:
                    new[new_key] = self.get(original, key)

    def run(self, original, article=None, new=None, skip_result=False):
        cp = self.new_current(original)
        new = new or {}
        if "<before>" in self.rules:
            self.apply(new, original, cp, self.rules["<before>"])
        for key in self.attrs(original):
            if key in self.rules:
                self.apply(new, original, cp, self.rules[key], key=key)
                self.indicate_usage(cp, key)
        if "<middle>" in self.rules:
            self.apply(new, original, cp, self.rules["<middle>"])
        for key, value in self.iterate_remaining(original, cp):
            setitem(new, key, value)

        if article is not None and "<article>" in self.rules:
            self.apply(new, article, cp, self.rules["<article>"])
        if "<after>" in self.rules:
            self.apply(new, original, cp, self.rules["<after>"])
        if "<result>" in self.rules and not skip_result:
            return self.process_element(self.rules["<result>"], new, original, cp)
        return new


class ConvertWork(ConvertDict):
    def has(self, original, key):
        return hasattr(original, key)

    def get(self, original, key):
        return getattr(original, key)

    def attrs(self, original):
        use = callable_get(self.rules, "<use>", dir(original))
        ignore = callable_get(self.rules, "<ignore>", [])
        for key in reversed(use):
            if hasattr(original, key) and not match_any(key, ignore):
                yield key

    def iterate_remaining(self, original, current):
        for key in self.attrs(original):
            if key not in current:
                yield key, str(getattr(original, key))

    def indicate_usage(self, current, key):
        current.add(key)

    def new_current(self, original):
        return set()


class ModifyRules(object):

    def __init__(self, rules, tag=None):
        self.rules = deepcopy(rules)
        self._enabled = True
        if tag is not None:
            if "<tags>" not in self.rules:
                self.rules["<tags>"] = set()
            if tag in self.rules["<tags>"]:
                self._enabled = False
            self.rules["<tags>"].add(tag)
                
    def append_all(self, key, values):
        if not self._enabled:
            return self
        if key not in self.rules:
            self.rules[key] = []
        for value in values:
            self.rules[key].append(value)
        return self

    def append(self, key, value):
        return self.append_all(key, [value])

    def prepend_all(self, key, values):
        if not self._enabled:
            return self
        temp = self.rules.get(key, [])
        self.rules[key] = values
        return self.append_all(key, temp)

    def prepend(self, key, value):
        return self.prepend_all(key, [value])

    def add_all(self, key, values):
        if not self._enabled:
            return self
        if key not in self.rules:
            self.rules[key] = set()
        for value in values:
            self.rules[key].add(value)
        return self

    def add(self, key, value):
        return self.add_all(key, {value})

    def replace(self, key, values):
        if not self._enabled:
            return self
        self.rules[key] = values
        return self


def old_form_to_new(show_deprecation=False):
    from . import config
    if show_deprecation:
        warnings.warn("""
            The following attributes have been deprecated:
                
            * config.FORM_BUTTONS
            
            * config.FORM_TEXT_FIELDS


            Please, consider upgrading to the new FORM definition format:

                config.FORM = {
                    'widgets': ...,
                    'order': ...,
                    'events': ...,
                }


            For obtaining an equivalent form definition, run:

                from snowballing.rules import old_form_to_new
                print(old_form_to_new())
        
        """)
    order = []
    widgets = []

    base = [
        [
            "dropdown", "Type", "work_type", config.DEFAULT_CLASS, 
            [tup[0] for tup in config.CLASSES]
        ],
        ["toggle", "File", "file_field", False],
        ["text", "Due", "due", ""],
        ["text", "Place", "place", ""],
        ["text", "Year", "year", ""],
        ["text", "Prefix Var", "prefix", ""],
        ["text", "PDFPage", "pdfpage", ""],
    ]

    events = [
        ["due", "observe", [
            ["if",
                ["and",
                    ["!=", ":due", ""],
                    ["==", ":work_type", "Work"]
                ],
                {
                    "work_type": "WorkUnrelated",
                },
                ["if",
                    ["and",
                        ["==", ":due", ""],
                        ["==", ":work_type", "WorkUnrelated"]
                    ],
                    {
                        "work_type": "Work"
                    },
                    []

                ]
            ]

        ]],
        ["place", "observe", [
            ["if",
                ["and",
                    ["==", ":place", "Lang"],
                    ["==", ":work_type", "Work"]
                ],
                {
                    "work_type": "WorkLang"
                },
                []
            ]
        ]],
    ]

    widgets = base[:]

    current_button = 0
    for row in config.FORM_BUTTONS:
        widget_row = []
        for button in row:
            current_button += 1
            button_id = "_b{}".format(current_button)
            widgets.append(["button", button[0], button_id])
            events.append([button_id, "click", {
                k.replace("_widget", ""): v for k, v in button[1].items()
            }])
            widget_row.append(button_id)
        order.append(widget_row)

    for tup in config.FORM_TEXT_FIELDS:
        new_tup = ["text", tup[0], tup[1], tup[2]]
        widgets.append(new_tup)
        base.append(new_tup)

    iterable = iter(base)
    for w1, w2 in zip_longest(iterable, iterable):
        order.append([w1[2]] + ([w2[2]] if w2 else []))

    return {
        "widgets": widgets,
        "order": order,
        "events": events,
    }