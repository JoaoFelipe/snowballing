from snowballing.approaches import Group

from ..constants import *
from ...work.y2014 import murta2014a
from ...work.y2015 import pimentel2015a


approach = Group(
    murta2014a, pimentel2015a,
    _display="no  Work  flow",
    _approach_name="noWorkflow",
    _cite=False,

    _meta=[dict(
        target=PYTHON,

    )],
    _about="""
        <p>
            noWorkflow (<a href="#murta2014a" class="reference">murta2014a</a>; <a href="#pimentel2015a" class="reference">pimentel2015a</a>) captures provenance from Python scripts for <span class="goal">comprehension</span>.
            <span class="collection">
                It requires no changes in the scripts for provenance collection. noWorkflow collects deployment, definition, and execution provenance.
            </span>
        </p>
    """,
)
