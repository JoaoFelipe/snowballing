"""This module provides functions to describe the snowballing strategies"""

import os
from collections import defaultdict, namedtuple, deque, Counter
from copy import copy
from snowballing.operations import load_citations, reload
from functools import reduce

from subprocess import Popen, PIPE as P

Step = namedtuple("Step", "name new_references new_related total_visited total_related source target")


class State(object):
    """Snowballing state"""

    last_id = -1

    def __init__(self, visited=None, related=None, filter_function=None, name=None):
        self.name = name or self.new_name()
        self.visited = copy(visited)
        self.related = copy(related)
        self.previous = []

        self.filter_function = filter_function
        self.last_visited_size = len(self.visited)

    def find(self, goal):
        """Find state by name"""
        stack = [self]
        visited = {id(self)}
        while stack:
            current = stack.pop()
            if goal == current.name:
                return current
            antecessors = current.previous[0] if current.previous else []
            for previous in antecessors:
                if id(previous) not in visited:
                    visited.add(id(previous))
                    stack.append(previous)
        return None

    def visit(self, work):
        """Visit work"""
        self.visited.add(work)
        if self.filter_function(work):
            self.related.add(work)

    def derive(self, operation, name=None):
        """Create a derived state"""
        new_state = State(self.visited, self.related, self.filter_function, name=name)
        new_state.previous = ([self], operation)
        return new_state

    def to_step(self, previous=None):
        """Convert SeedSet to Step"""
        previous = previous or self.previous
        if not previous:
            operation, last_name = "start", ""
            prev_visited = prev_related = set()
        else:
            seeds, operation = previous
            last_name = "|".join(x.name for x in seeds)
            prev_visited = reduce(lambda x, y: x | y.visited, seeds, set())
            prev_related = reduce(lambda x, y: x | y.related, seeds, set())
        return Step(
            operation,
            len(self.visited - prev_visited), len(self.related - prev_related),
            len(self.visited), len(self.related),
            last_name, self.name
        )

    @property
    def log(self):
        """Creates log list"""
        stack = deque([self])
        result = deque()
        visited = {id(self)}
        while stack:
            current = stack.popleft()
            result.appendleft(current.to_step())
            if current.previous:
                for element in current.previous[0]:
                    if id(element) not in visited:
                        stack.append(element)
                        visited.add(id(element))
        return result

    @property
    def provn(self):
        """Convert state provenance into provn

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> print(Strategy({murta2014a}).fbfb().provn)
            document
              default <http://example.org/>
            <BLANKLINE>
              entity(s2, [type="Set", visited="3", related="1"])
              activity(backward2, -, -, [found="1", related="0"])
              used(u0; backward2, s1, -)
              wasGeneratedBy(g0; s2, backward2, -)
              wasDerivedFrom(s2, s1, backward2, g0, u0, [prov:type="prov:Revision"])
            <BLANKLINE>
              entity(s1, [type="Set", visited="2", related="1"])
              activity(forward1, -, -, [found="1", related="0"])
              used(u1; forward1, s0, -)
              wasGeneratedBy(g1; s1, forward1, -)
              wasDerivedFrom(s1, s0, forward1, g1, u1, [prov:type="prov:Revision"])
            <BLANKLINE>
              entity(s0, [type="Set", visited="1", related="1"])
              activity(start, -, -)
              wasGeneratedBy(g2; s0, start, -)
            <BLANKLINE>
            endDocument
        """
        result = ["document", "  default <http://example.org/>", ""]
        actions = Counter()

        stack = deque([self])
        visited = {id(self)}
        while stack:
            current = stack.popleft()
            result.append('  entity({}, [type="Set", visited="{}", related="{}"])'.format(
                current.name, len(current.visited), len(current.related)
            ))
            if current.previous:
                name = current.previous[1]
                activity_id = "{}{}".format(name, current.name[1:])

                result.append('  activity({}, -, -, [found="{}", related="{}"])'.format(
                    activity_id, len(current.delta_visited), len(current.delta_related)
                ))

                for element in current.previous[0]:
                    used_id = "u{}".format(actions["used"])
                    actions["used"] += 1
                    result.append('  used({}; {}, {}, -)'.format(used_id, activity_id, element.name))
                    generated_id = "g{}".format(actions["generated"])
                    actions["generated"] += 1
                    result.append('  wasGeneratedBy({}; {}, {}, -)'.format(
                        generated_id, current.name, activity_id)
                    )
                    result.append('  wasDerivedFrom({}, {}, {}, {}, {}, [prov:type="prov:Revision"])'.format(
                        current.name, element.name, activity_id, generated_id, used_id
                    ))
                    if id(element) not in visited:
                        stack.append(element)
                        visited.add(id(element))
            else:
                generated_id = "g{}".format(actions["generated"])
                actions["generated"] += 1
                result.append("  activity(start, -, -)")
                result.append('  wasGeneratedBy({}; {}, start, -)'.format(
                    generated_id, current.name)
                )
            result.append("")

        result.append("endDocument")
        return '\n'.join(result)

    @property
    def dot(self):
        """Convert state provenance into dot

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> print(Strategy({murta2014a}).fbfb().dot)
            digraph G {
              rankdir="RL";
            <BLANKLINE>
              s2 [label="s2\\nvisited: 3\\nrelated: 1"];
              s2 -> s1 [label="backward\\nfound: 1\\nrelated: 0"];
            <BLANKLINE>
              s1 [label="s1\\nvisited: 2\\nrelated: 1"];
              s1 -> s0 [label="forward\\nfound: 1\\nrelated: 0"];
            <BLANKLINE>
              s0 [label="s0\\nvisited: 1\\nrelated: 1"];
            <BLANKLINE>
            }
            >>> None
        """
        result = ["digraph G {", '  rankdir="RL";', ""]
        actions = Counter()

        stack = deque([self])
        visited = {id(self)}
        while stack:
            current = stack.popleft()
            result.append('  {0} [label="{0}\\nvisited: {1}\\nrelated: {2}"];'.format(
                current.name, len(current.visited), len(current.related)
            ))
            if current.previous:
                operation = current.previous[1]
                for element in current.previous[0]:
                    result.append('  {} -> {} [label="{}\\nfound: {}\\nrelated: {}"];'.format(
                        current.name, element.name, operation,
                        len(current.delta_visited), len(current.delta_related)
                    ))
                    if id(element) not in visited:
                        stack.append(element)
                        visited.add(id(element))
            result.append("")

        result.append("}")
        return '\n'.join(result)

    @property
    def delta_related(self):
        """Compares number of related"""
        last = set()
        if self.previous:
            last = reduce(lambda x, y: x | y.related, self.previous[0], set())
        return self.related - last

    @property
    def delta_visited(self):
        """Compares number of related"""
        last = set()
        if self.previous:
            last = reduce(lambda x, y: x | y.visited, self.previous[0], set())
        return self.visited - last

    def __iter__(self):
        """Frontier generator. Generates related"""
        for work in self.related:
            yield work

    def __nonzero__(self):
        return bool(self.new_frontier)

    def __bool__(self):
        return bool(self.new_frontier)

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {}

        dot = self.dot
        bundle['text/vnd.graphviz'] = dot

        try:
            kwargs = {} if os.name != 'nt' else {"creationflags": 0x08000000}
            p = Popen(['dot', '-T', "svg"], stdout=P, stdin=P, stderr=P, **kwargs)
            image = p.communicate(dot.encode('utf-8'))[0]
            bundle['image/svg+xml'] = image.decode("utf-8")
        except OSError as e:
            if e.errno != os.errno.ENOENT:
                raise

        bundle['text/plain'] = '\n'.join(map(str, self.log))
        display(bundle, raw=True)

    @classmethod
    def new_name(cls):
        """Generate new name for SeedSet"""
        cls.last_id += 1
        return "s{}".format(cls.last_id)

    @classmethod
    def union(cls, first, second, operation="union", name=None):
        """Create a joined state"""
        new_state = first.derive(operation, name=name)
        new_state.visited.update(second.visited)
        new_state.related.update(second.related)
        new_state.previous[0].append(second)
        return new_state


class Strategy(object):
    """Base Strategy class

    Arguments:

    * `initial_set` -- start set of the snowballing

    Keyword arguments:

    * `filter_function` -- function for filtering results

      * By default it selects work with category == 'snowball'

    * `visited` -- visited set of the start start

      * By default it is the initial_set

    """

    def __init__(self, initial_set, filter_function=None, visited=None):

        if filter_function is None:
            filter_function = lambda x: x.category == "snowball"

        reload()
        State.last_id = -1
        self.initial = State(visited or initial_set, initial_set, filter_function)

        self.ref = defaultdict(list)
        self.rev_ref = defaultdict(list)
        for cit in load_citations():
            self.ref[cit.work].append(cit.citation)
            self.rev_ref[cit.citation].append(cit.work)

    def backward(self, state=None):
        """Follow backward references on frontier

        Returns new frontier and target set name"""
        state = self.initial if state is None else state
        new_state = state.derive("backward")
        for work in state:
            for cited in self.ref[work]:
                new_state.visit(cited)
        return new_state

    def forward(self, state=None):
        """Follow forward references on frontier

        Returns new frontier and target set name"""
        state = self.initial if state is None else state
        new_state = state.derive("forward")
        for work in state:
            for citer in self.rev_ref[work]:
                new_state.visit(citer)
        return new_state

    def _repeat(self, order, max_count, state=None):
        """Alternates functions in order"""
        state = self.initial if state is None else state
        count = 0
        first = 1
        running = True
        while running:
            for func in order:
                count = (count + 1) if not state.delta_related else 0
                if count >= max_count + first:
                    running = False
                    break
                state = func(state)
                first = 0
        return state

    def fbfb(self, state=None):
        """Alternates forward and backward

        (FB)*::

            s0 <-f- s1 <-b- s2 <-f- s3 <-b- s4

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).fbfb()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        return self._repeat([self.forward, self.backward], 2, state)

    def bfbf(self, state=None):
        """Alternates backward and forward

        (BF)*::

            s0 <-b- s1 <-f- s2 <-b- s3 <-f- s4

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).fbfb()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        return self._repeat([self.backward, self.forward], 2, state)

    def bb(self, state=None):
        """Apply sequences of backward

        B*::

            s0 <-b- s1 <-b- s2

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).bb()
            >>> len(state.related)
            1
            >>> len(state.visited)
            2
        """
        return self._repeat([self.backward], 1, state)

    def ff(self, state=None):
        """Apply sequences of forward

        F*::

            s0 <-f- s1 <-f- s2

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).ff()
            >>> len(state.related)
            1
            >>> len(state.visited)
            2
        """
        return self._repeat([self.forward], 1, state)

    def bbff(self, state=None):
        """Apply sequences of backward. Then apply sequences of forward

        B*F*::

            s0 <-b- s1 <-b- s2 <-f- s3 <-f- s4

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).bbff()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        state = self.bb(state)
        return self.ff(state)

    def ffbb(self, state=None):
        """Apply sequences of forward. Then apply sequences of backward

        F*B*::

            s0 <-f- s1 <-f- s2 <-b- s3 <-b- s4

        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).ffbb()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        state = self.ff(state)
        return self.bb(state)

    def sbfu(self, state=None):
        """Apply forward and backward in parallel once, join results and repeat

        S(B, F)*::

                f - s1           f - s4
              /        \       /        \\
            s0           U - s3           U - s6
              \        /       \        /
                b - s2           b - s5


        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).sbfu()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        state = self.initial if state is None else state
        while True:
            fstate = self.forward(state)
            bstate = self.backward(state)
            state = State.union(fstate, bstate)
            if not fstate.delta_related and not bstate.delta_related:
                return state

    sfbu = sbfu

    def s2bbff2u(self, state=None):
        """Apply all forward and all backward in parallel. Then join

        S(B*, F*)::

                f - s1 <-f- s2
              /                \\
            s0                   U - s5
              \                /
                b - s3 <-b- s4


        Doctest:

        .. doctest::

            >>> from .operations import reload, work_by_varname
            >>> reload()
            >>> murta2014a = work_by_varname("murta2014a")
            >>> state = Strategy({murta2014a}).s2ffbb2u()
            >>> len(state.related)
            1
            >>> len(state.visited)
            3
        """
        state = self.initial if state is None else state
        fstate = self.ff(state)
        bstate = self.bb(state)
        return State.union(fstate, bstate)

    s2ffbb2u = s2bbff2u
