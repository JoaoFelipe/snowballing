"""This module includes common places in the database and provides functions
for creating other places

It includes the following common places in the database:

* Book -- represents books
* Lang -- represents places in foreign language
* Patent -- represents patents
* Standard -- represents standards
* TechReport -- represents technical reports
* Thesis -- represents thesis
* Unpublished -- represents work that were not published
* Web -- represents websites

"""
from .models import Place, DB


def conference(acrom, name, **kwargs):
    """Create a place with 'Conference' type"""
    return DB(Place(acrom, name, "Conference", **kwargs))


def journal(acrom, name, **kwargs):
    """Create a place with 'Journal' type"""
    return DB(Place(acrom, name, "Journal", **kwargs))


def magazine(acrom, name, **kwargs):
    """Create a place with 'Magazine' type"""
    return DB(Place(acrom, name, "Magazine", **kwargs))


Book = DB(Place("Book", "Book", "Book"))
Lang = DB(Place("Lang", "Lang", "Lang"))
Patent = DB(Place("Patent", "Patent", "Patent"))
Standard = DB(Place("Standard", "Standard", "Standard"))
TechReport = DB(Place("Tech Report", "Tech Report", "Tech Report"))
Thesis = DB(Place("Thesis", "Thesis", "Thesis"))
Unpublished = DB(Place("Unpublished", "Unpublished", "Unpublished"))
Web = DB(Place("Web", "Web", "Web"))
