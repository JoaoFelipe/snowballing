from snowballing.models import Place, DB
from snowballing.common_places import *

CiSE = journal("CiSE", "Computing in Science & Engineering")
ICSE = conference("ICSE", "International Conference on Software Engineering")
IPAW = conference("IPAW", "International Provenance and Annotation Workshop")
TaPP = conference("TaPP", "Workshop on the Theory and Practice of Provenance")


arXiv = DB(Place("arXiv", "arXiv", "Archive"))
