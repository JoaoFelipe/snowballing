# coding: utf-8
from datetime import datetime
from snowballing.models import *
from ..places import *

murta2014a = DB(WorkSnowball(
    2014, "noWorkflow: capturing and analyzing provenance of scripts",
    aliases=[  # List of aliases for the same work
        (
            2015, 
            "noWorkflow: Capturing and Analyzing Provenance of Scripts",
            "Chirigati, Fernando and Koop, David and Freire, Juliana"
        ),
    ],
    snowball=datetime(2017, 3, 6),
    display="noWorkflow",
    authors="Murta, Leonardo and Braganholo, Vanessa and Chirigati, Fernando and Koop, David and Freire, Juliana",
    place=IPAW,
    local="Cologne, Germany",
    file="murta2014a.pdf",
    scholar="http://scholar.google.com/scholar?cites=5458343950729529273&as_sdt=2005&sciodt=0,5&hl=en",
    scholar_id="ucciVefuv0sJ",
    scholar_id2="FiutAE4j0IgJ",
    pp="71--83",
    entrytype="inproceedings",
    organization="Springer",
    cluster_id="5458343950729529273",
    scholar_ok=True,
    citation_file="murta2014a",
    tracking="alert",
))
