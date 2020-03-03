# coding: utf-8
from snowballing.models import *
from snowballing import dbindex
dbindex.last_citation_file = dbindex.this_file(__file__)

from ..work.y2008 import freire2008a
from ..work.y2014 import murta2014a
from ..work.y2015 import pimentel2015a

DB(Citation(
    murta2014a, freire2008a, ref="[5]",
    contexts=[
        "There are two types of provenance for scientific workflows: prospective and retrospective [5]. Prospective provenance describes the structure of the experiment and corresponds to the workflow definition, the graph of the activities, and their associated parameters. Retrospective provenance captures the steps taken during the workflow execution, and while it has similar (graph) structure, it is constructed using information collected at runtime, including activities invoked and parameter values used, intermediate data produced, the execution start and end times, etc"
    ],
))

DB(Citation(
    pimentel2015a, murta2014a, ref="",
    contexts=[

    ],
))
