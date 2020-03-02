"""This module contains operations to manipulate the database

Warning: since it involves manipulating source code, some operations may not be
very reliable.

Additionaly, we currently do not have tests for this file.
Thus, my suggestion is to use only the :meth:`~insert` and :meth:`~set_attribute` functions.
These functions were heavily used during my snowballing.

For other operations, such as removing citations/work, I recommend editting
files manually.
"""

import pyposast
import ast
import warnings
import os
import re

from collections import defaultdict
from .operations import reload, work_by_varname, load_citations
from .dbindex import year_file, citation_file, parse_varname, discover_year
from .dbindex import increment_str
from .utils import compare_str


class ReplaceOperation(object):
    """Operation for replacing `.target` lines by `:value`"""

    def __init__(self, target):
        self.first_line = target.first_line - 1
        self.first_col = target.first_col
        self.last_line = target.last_line - 1
        self.last_col = target.last_col

    def apply(self, lines, value):
        """Replace `lines` of `:target` by `:value`"""
        lines[self.first_line] = (
            lines[self.first_line][:self.first_col] + value
            + lines[self.last_line][self.last_col:]
        )
        for line in range(self.last_line, self.first_line, -1):
            del lines[line]


class DelOperation(object):
    """Operation for removing `.keyword`"""
    def __init__(self, keyword, delete_lines=False):
        self.keyword = keyword
        self.delete_lines = delete_lines

    def apply(self, lines, value):
        """Remove `.keyword` from `:lines`"""
        replace = ReplaceOperation(self.keyword)
        replace.apply(lines, "")
        if self.delete_lines:
            del lines[replace.first_line]
            while replace.first_line < len(lines) and not lines[replace.first_line]:
                del lines[replace.first_line]


class AddKeywordOperation(object):
    """Operation for adding `:attribute`"""
    def __init__(self, attribute, last_line):
        self.last_line = last_line
        self.attribute = attribute

    def apply(self, lines, value):
        """Add `.attribute` = `:value` into `:lines`"""
        lines.insert(
            self.last_line,
            "    {}={},".format(
                self.attribute, value
            )
        )


class InsertOperation(object):
    """Operation for inserting values in a given line"""
    def __init__(self, last_line, last=False, add_line=True):
        self.last_line = last_line - 1
        self.last = last
        self.add_line = add_line

    def apply(self, lines, value):
        """Insert `:value` at line `.last_line`"""
        new_entry = value.split("\n")
        if self.add_line:
            new_entry.append("")

        line = self.last_line
        if self.last:
            if lines[-1]:
                lines.append("")
            line = len(lines)
        lines[line:line] = new_entry


class DetectOperation(object):
    """Operation for detecting elements"""

    def __init__(self):
        self.work_list = []
        self.citations = []
        self.imports = []

    def apply(self, lines, value):
        """Detect elements"""
        value["work_list"] = self.work_list
        value["citations"] = self.citations
        value["imports"] = self.imports


def is_assign_to_name(stmt):
    """Check if stmt is an assignment to name"""
    return (
        isinstance(stmt, ast.Assign) and
        isinstance(stmt.targets[0], ast.Name)
    )


def is_call_statement(stmt):
    """Check if stmt is a call expr"""
    return (
        isinstance(stmt, ast.Expr) and
        isinstance(stmt.value, ast.Call)
    )


class EditVisitor(ast.NodeVisitor):
    """Visitor for editing attributes of a Work identified by `.varname`"""
    def __init__(self, lines, varname, operation="rename"):
        self.varname = varname
        self.operation = operation
        self.result = None
        self.old = ""
        self.lines = lines

    def replace(self, node):
        """Instantiate a replace operation"""
        self.result = ReplaceOperation(node)
        self.old = pyposast.extract_code(self.lines, node)

    def add_keyword(self, attribute, last_line):
        """Instantiate an operation to add keyword"""
        self.result = AddKeywordOperation(attribute, last_line)
        self.old = ""

    def remove_keyword(self, keyword, remove_lines):
        """Instantiate an operation to remove a keyword"""
        if not remove_lines:
            warnings.warn(
                "PyPosAST bug"
                "Wrong positions for keywords. Won't delete attribute"
            )
        self.result = DelOperation(keyword.value, remove_lines)
        self.old = keyword.arg + "=" + pyposast.extract_code(
            self.lines, keyword.value)

    def visit_Assign(self, node):
        """Visits assign and check if it represents the desired `.varname`

        Then, instantiate and apply the desired `.operation`
        """
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == self.varname:
                if self.operation == "rename":
                    self.replace(target)
                elif self.operation == "set year":
                    self.replace(node.value.args[0].args[0])
                elif self.operation == "set name":
                    self.replace(node.value.args[0].args[1])
                elif self.operation == "set class":
                    self.replace(node.value.args[0].func)
                elif self.operation.startswith("set "):
                    attribute = self.operation.split()[1]
                    last_line = node.value.args[0].args[1].last_line
                    for keyword in node.value.args[0].keywords:
                        if keyword.arg == attribute:
                            self.replace(keyword.value)
                            break
                        last_line = max(last_line, keyword.value.last_line)
                    else:
                        self.add_keyword(attribute, last_line)
                elif self.operation.startswith("del "):
                    attribute = self.operation.split()[1]
                    lines = defaultdict(set)
                    for keyword in node.value.args[0].keywords:
                        lines[keyword.first_line].add(keyword)
                        lines[keyword.last_line].add(keyword)
                    for keyword in node.value.args[0].keywords:
                        if keyword.arg == attribute:
                            self.remove_keyword(
                                keyword,
                                (len(lines[keyword.first_line]) == 1 and
                                 len(lines[keyword.last_line]) == 1)
                            )


class BodyVisitor(ast.NodeVisitor):
    """Visit body of year file to find `.varname` and apply `.operation`"""

    def __init__(self, lines, varname, operation="delete"):
        self.varname = varname
        self.operation = operation
        self.result = None
        self.lines = lines
        self.old = ""

    def remove_stmt(self, stmt):
        """Instantiate an operation to remove the stmt"""
        self.result = DelOperation(stmt, True)
        self.old = pyposast.extract_code(self.lines, stmt)

    def insert(self, line, last):
        """Instantiate an operation to insert code"""
        self.result = InsertOperation(line, last)
        self.old = ""

    def process_body(self, body):
        """Finds desired varnames in body and instantiate operation"""
        oper = self.operation
        lines = self.lines
        if oper == "detect":
            self.result = DetectOperation()
        for stmt in body:
            if is_assign_to_name(stmt):
                if stmt.targets[0].id == self.varname and oper == "delete":
                        self.remove_stmt(stmt)
                        break
                elif stmt.targets[0].id > self.varname and oper == "insert":
                    self.insert(stmt.first_line, False)
                    break
                elif self.operation == "detect":
                    self.result.work_list.append((
                        stmt.targets[0].id,
                        stmt.value.args[0].args[1].s,
                        pyposast.extract_code(lines, stmt),
                        stmt.value.args[0].args[0].n,
                    ))
            elif self.operation == "detect" and is_call_statement(stmt):
                self.result.citations.append((
                    pyposast.extract_code(lines, stmt.value.args[0].args[0]),
                    pyposast.extract_code(lines, stmt.value.args[0].args[1]),
                    pyposast.extract_code(lines, stmt.value),
                    isinstance(stmt.value.args[0].args[1], ast.Name),
                ))
        if body and self.operation == "insert" and not self.result:
            self.insert(stmt.last_line, True)

    def visit_Interactive(self, node):
        """Process body of Interactive node"""
        self.process_body(node.body)

    def visit_Module(self, node):
        """Process body of Module node"""
        self.process_body(node.body)

    def visit_Suite(self, node):
        """Processes body of Suite node"""
        self.process_body(node.body)


class CitationVisitor(ast.NodeVisitor):
    """Visit body of citation file to apply operation"""

    def __init__(self, lines, varname, year, operation="remove import"):
        self.varname = varname
        self.year = int(year)
        self.operation = operation
        self.result = None
        self.old = ""
        self.lines = lines

    def process_body(self, body):
        """Find citation/import and applies the desired `.operation`"""
        if self.operation in ("find", "detect"):
            self.result = DetectOperation()
        last_line = 0
        for stmt in body:
            if isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
                year = int(getattr(re.search(r"work\.y(\d\d\d\d)", stmt.module), "group", lambda x: -1)(1))
                if self.year == year and self.operation == "remove import":
                    aliases = [a for a in stmt.names if a.name == self.varname]
                    if aliases:
                        if len(stmt.names) == 1:
                            self.result = DelOperation(stmt, True)
                            self.old = pyposast.extract_code(self.lines, stmt)
                        elif aliases[0] == stmt.names[-1]:
                            line = "".join(reversed(self.lines[aliases[0].last_line - 1]))
                            pos = len(line) - aliases[0].first_col
                            aliases[0].first_col = len(line) - next(re.compile("\w.*").finditer(line, pos=pos)).span()[0]
                            self.result = DelOperation(aliases[0], False)
                            self.old = pyposast.extract_code(self.lines, aliases[0])
                        else:
                            line = self.lines[aliases[0].last_line - 1]
                            pos = aliases[0].last_col
                            aliases[0].last_col = next(re.compile("\w.*").finditer(line, pos=pos)).span()[0]
                            self.result = DelOperation(aliases[0], False)
                            self.old = pyposast.extract_code(self.lines, aliases[0])
                        break
                if self.operation == "insert import":
                    last_line = stmt.first_line
                    if self.year < year:
                        self.result = InsertOperation(stmt.first_line, False, add_line=False)
                        break
                if year != -1 and self.operation == "detect":
                    self.result.imports += [a.name for a in stmt.names]
            if is_call_statement(stmt):
                if self.operation == "insert import":
                    self.result = InsertOperation(last_line + 1, False, add_line=False)
                    break
                target = pyposast.extract_code(self.lines, stmt.value.args[0].args[1])
                source = pyposast.extract_code(self.lines, stmt.value.args[0].args[0])
                if self.operation == "remove target" and target == self.varname:
                    self.result = DelOperation(stmt, True)
                    self.old = source + "<=>" + pyposast.extract_code(self.lines, stmt)
                    break
                if self.operation == "remove source" and source == self.varname:
                    self.result = DelOperation(stmt, True)
                    self.old = target + "<=>" + pyposast.extract_code(self.lines, stmt)
                    break
                if self.operation == "find" and self.varname in (source, target):
                    self.result.citations.append(self.varname)
                if self.operation == "detect":
                    self.result.citations.append((source, target))

        if self.operation == "insert import" and not self.result:
            self.result = InsertOperation(last_line + 1, True, add_line=True)

    def visit_Interactive(self, node):
        """Process body of Interactive node"""
        self.process_body(node.body)

    def visit_Module(self, node):
        """Process body of Module node"""
        self.process_body(node.body)

    def visit_Suite(self, node):
        """Processes body of Suite node"""
        self.process_body(node.body)


def read_file(filename):
    """Read python file with the right codec"""
    with open(filename, "rb") as script_file:
        code = pyposast.native_decode_source(script_file.read())
    sep = "\r\n" if "\r" in code else "\n"
    lines = code.split(sep)
    return lines, sep


def save_lines(filename, lines, sep="\n"):
    """Write python file with utf-8"""
    with open(filename, "wb") as script_file:
        script_file.write(sep.join(lines).encode("utf-8"))


def work_operation(filename, lines, varname, operation, value=""):
    """Apply `:operation` for `:varname` in a year file `:filename`"""
    vis_class = EditVisitor
    if operation in ("delete", "insert", "detect"):
        vis_class = BodyVisitor
    visitor = vis_class(lines, varname, operation)
    tree = pyposast.parse("\n".join(lines), filename)
    visitor.visit(tree)
    if not visitor.result:
        return visitor, False
    visitor.result.apply(lines, value)
    return visitor, True


def citation_operation(filename, lines, varname, year, operation, value=""):
    """Apply `:operation` for `:varname` in a citation file `:filename`"""
    visitor = CitationVisitor(lines, varname, year, operation)
    if operation == "rename":
        regex = re.compile(varname + r"\s*?,")
        for i, line in enumerate(lines):
            lines[i] = regex.sub(value + ",", line)
        return visitor, True
    elif operation == "insert citation":
        if lines[-1]:
            lines.append("")
        lines.append("")
        lines[-1:-1] = value.split("\n")
        if lines[-1]:
            lines.append("")
        return visitor, True
    tree = pyposast.parse("\n".join(lines), filename)
    visitor.visit(tree)
    if not visitor.result:
        return visitor, False
    if operation == "insert import":
        value = "from ..work.y{} import {}".format(year, varname)
    visitor.result.apply(lines, value)
    return visitor, True


def rename_citation(name, original_varname, new_varname, year=None, new_year=None, dry_run=False):
    """Rename citation varname"""
    year = discover_year(original_varname, year)
    new_year = discover_year(new_varname, new_year, fail_raise=False) or year
    filename = citation_file(name)
    lines, sep = read_file(filename)
    print("-Remove Import:", original_varname)
    citation_operation(filename, lines, original_varname, year, "remove import")
    print("-Insert Import:", new_varname)
    citation_operation(filename, lines, new_varname, new_year, "insert import")
    print("-Rename References:", original_varname, "to", new_varname)
    citation_operation(filename, lines, original_varname, year, "rename", new_varname)

    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def remove_source_citation(name, varname, year=None, dry_run=False):
    """Remove citation where the citer is `:varname`"""
    year = discover_year(varname, year)
    filename = citation_file(name)
    lines, sep = read_file(filename)

    targets = []
    doing = True
    while doing:
        visitor, doing = citation_operation(filename, lines, varname, year, "remove source")
        target = visitor.old.split("<=>")[0]
        print("-Remove Citation:", varname, "->", target)
        tyear = re.search(r"\d\d\d\d", target)
        if tyear:
            targets.append((target, int(tyear.group(0))))

    print("-Remove Import:", varname)
    citation_operation(filename, lines, varname, year, "remove import")
    for target in targets:
        result = {}
        citation_operation(filename, lines, target[0], target[1], "find", result)
        if not result["citations"]:
            print("-Remove Import:", target[0])
            citation_operation(filename, lines, target[0], target[1], "remove import")

    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def remove_target_citation(name, varname, year=None, dry_run=False):
    """Remove citation where the cited is `:varname`"""
    year = discover_year(varname, year)
    filename = citation_file(name)
    lines, sep = read_file(filename)

    sources = []
    doing = True
    while doing:
        visitor, doing = citation_operation(filename, lines, varname, year, "remove target")
        source = visitor.old.split("<=>")[0]
        print("-Remove citation:", source, "->", varname)
        syear = re.search(r"\d\d\d\d", source)
        if syear:
            sources.append((source, int(syear.group(0))))

    print("-Remove Import:", varname)
    citation_operation(filename, lines, varname, year, "remove import")
    for source in sources:
        result = {}
        citation_operation(filename, lines, source[0], source[1], "find", result)
        if not result["citations"]:
            print("-Remove Import:", source[0])
            citation_operation(filename, lines, source[0], source[1], "remove import")

    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def insert_citation(name, text, dry_run=False):
    """Insert citation by `:text` in file `:name`"""
    filename = citation_file(name)
    try:
        lines, sep = read_file(filename)
    except FileNotFoundError:
        lines = [
            "# coding: utf-8",
            "from snowballing.models import *",
            "from snowballing import dbindex",
            "dbindex.last_citation_file = dbindex.this_file(__file__)",
            "",
        ]
        sep = "\n"
    result = {}
    citation_operation(filename, lines, "", 0, "detect", result)
    imports = set(result["imports"])
    citations = result["citations"]
    result = {}
    citation_operation(filename, text.split("\n"), "", 0, "detect", result)
    for source, target in result["citations"]:
        if (source, target) in citations:
            warnings.warn("Repeated citation: {} -> {}".format(source, target))
        if not source in imports:
            year = parse_varname(source, 2)
            if year is not None:
                print("-Insert Import:", source)
                citation_operation(filename, lines, source, year, "insert import")
        if not target in imports:
            year = parse_varname(target, 2)
            if year is not None:
                print("-Insert Import:", target)
                citation_operation(filename, lines, target, year, "insert import")
        print("-Insert Citation:", source, "->", target)
    citation_operation(filename, lines, "", 0, "insert citation", text)
    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def insert_work(varname, name, text, year=None, ratio=0.9, dry_run=False):
    """Insert work by `:text` in file `:name`"""
    year = discover_year(varname, year)
    filename = year_file(year)
    try:
        lines, sep = read_file(filename)
    except FileNotFoundError:
        lines = [
            "# coding: utf-8",
            "from datetime import datetime",
            "from snowballing.models import *",
            "from ..places import *",
            ""
        ]
        sep = "\n"
    result = {}
    work_operation("", lines, "", "detect", result)
    letter = ""
    for db_varname, db_name, _, db_year in result["work_list"]:
        if db_varname.startswith(varname):
            if compare_str(name, db_name) > ratio:
                print("Same:", db_varname)
                return db_varname, []
            splitted = db_varname.split(str(db_year))
            if splitted[-1]:
                letter = max(increment_str(splitted[-1]), letter, key=lambda x: (len(x), x))
            else:
                rename_lines(filename, lines, sep, db_year, db_varname, db_varname + "a", dry_run=dry_run)
                letter = "b"
                break
    newname = varname + letter
    print("-Insert:", newname)
    work_operation(filename, lines, varname + letter, "insert", text.replace(varname, newname))
    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return newname, lines


def rename_work(original_name, new_name, year=None, new_year=None, citations=True, dry_run=False):
    """Rename work"""
    year = discover_year(original_name, year)
    new_year = discover_year(new_name, new_year, fail_raise=False) or year
    filename = year_file(year)
    lines, sep = read_file(filename)
    rename_lines(filename, lines, sep, original_name, new_name, year=year, new_year=new_year,
                 citations=citations, dry_run=dry_run)
    return lines


def rename_lines(filename, lines, sep, original_name, new_name, year=None, new_year=None, citations=True, dry_run=False):
    """Rename work in year and citation files"""
    year = discover_year(original_name, year)
    new_year = discover_year(new_name, new_year, fail_raise=False) or year
    print("-Rename:", original_name, "to", new_name)
    work_citations = set()
    if citations or year != new_year:
        reload()
        work = work_by_varname(original_name)
    if citations:
        reload()
        work_citations = {
            cit._citations_file for cit in load_citations()
            if cit.citation == work or cit.work == work
        }
    if year != new_year:
         work_operation(filename, lines, original_name, "set year", str(new_year))
    work_operation(filename, lines, original_name, "rename", new_name)
    visitor, applied = work_operation(filename, lines, new_name, "delete")
    if year != new_year:
        rlines = insert_work(new_name, work.name, visitor.old, year=new_year, dry_run=dry_run)[1]
        if dry_run:
            print("\n".join(["y{}".format(new_year), "", ""] + rlines))
    else:
        work_operation(filename, lines, new_name, "insert", visitor.old)

    for citation in work_citations:
        rlines = rename_citation(citation, original_name, new_name, year=year, new_year=new_year, dry_run=dry_run)
        if dry_run:
            print("\n".join([citation, "", ""] + rlines))
    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def set_attribute(varname, field, value, year=None, dry_run=False):
    """Set attribute for work

    Arguments:

    * `varname` -- work variable name

    * `field` -- work attribute name

    * `value` -- new value for attribute

    Keyword arguments:

    * `year` -- limit work search for specific year

    * `dry_run` -- do not apply changes to the database

    Example::

        set_attribute('murta2014a', "display", "now");
    """
    year = discover_year(varname, year)
    filename = year_file(year)
    lines, sep = read_file(filename)
    if field not in ("year", "class", "place", "snowball") and isinstance(value, str):
        value = '"{}"'.format(str(value).replace('"', '\\"'))
    else:
        value = str(value)
    work_operation(filename, lines, varname, "set {}".format(field), value)
    if not dry_run:
        save_lines(filename, lines, sep=sep)
    return lines


def insert(text, citations=None, ratio=0.9, dry_run=False):
    """Insert text that might contain works and citations.

    Arguments:

    * `text` -- code with work and citations

    Keyword arguments:

    * `citations` -- citations filename

    * `ratio` -- comparison threshold for existing work

    * `dry_run` -- do not apply changes to the database

    Example::

        insert('''
        pimentel2016a = DB(WorkSnowball(
            2016, "Tracking and analyzing the evolution of provenance from scripts",
            display="noworkflow a",
            authors="Pimentel, João Felipe and Freire, Juliana and Braganholo, Vanessa and Murta, Leonardo",
            place=IPAW,
            pp="16--28",
            entrytype="inproceedings",
        ))

        DB(Citation(
            pimentel2016a, murta2014a, ref="[14]",
            contexts=[
            ],
        ))
        ''', citations="murta2014a");

    """
    result = {}
    lines = text.split("\n")
    work_operation("", lines, "", "detect", result)

    newnames = {}
    for work in result["work_list"]:
        newnames[work[0]] = insert_work(*work, ratio=ratio, dry_run=dry_run)[0]
    if citations:
        for source, target, text, cited_is_name in result["citations"]:
            lines2 = text.split("\n")
            for key, value in newnames.items():
                citation_operation(citations, lines2, key, 0, "rename", value)
            insert_citation(citations, "\n".join(lines2), dry_run=dry_run)
    return result
