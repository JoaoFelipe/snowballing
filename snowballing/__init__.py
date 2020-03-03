""" Snowballing tools """
import argparse
import os
import sys
import subprocess

from os.path import join, dirname, exists
from pathlib import Path
from pkg_resources import resource_string, resource_listdir, resource_isdir


def resource(filename, encoding=None):
    """Access resource content via setuptools"""
    content = resource_string(__name__, filename)
    if encoding:
        return content.decode(encoding=encoding)
    return content


def recursive_copy(origin, destiny):
    """Copy directory from resource to destiny folder"""
    if resource_isdir(__name__, origin):
        if not exists(destiny):
            os.makedirs(destiny)
        for element in resource_listdir(__name__, origin):
            origin_element = join(origin, element)
            destiny_element = join(destiny, element)
            recursive_copy(origin_element, destiny_element)
    else:
        with open(destiny, "wb") as fil:
            fil.write(resource(origin))


def start(args):
    """ Create a new literature snowballing folder """
    profiles = {
        "default": "example",
        "bibtex": "bibtex"
    }
    profile = args.profile.lower()
    if profile not in profiles:
        print("Profile {} not found!".format(profile))
        profile = "default"
    print("Using {} profile".format(profile))
    print("Creating {}".format(args.path))
    recursive_copy(profiles[profile], args.path)
    print("Done!")


def search(args):
    """ Search references in the database """
    try:
        sys.path.append(os.getcwd())

        import database
        from .operations import load_work, work_to_bibtex, reload, find
        reload()
        results = {x for x in find(args.query)}
        for work in results:
            print(work_to_bibtex(work))

    except ImportError:
        print("You must execute this command inside the project folder!")
        raise


def web(args):
    """ Start web server """
    try:
        sys.path.append(os.getcwd())
        import database
        my_env = os.environ.copy()
        my_env["FLASK_APP"] = os.path.join(os.path.dirname(__file__), "web.py")
        my_env["FLASK_ENV"] = "development"
        cmd = [sys.executable, "-m", "flask", "run"]
        if args.host:
            cmd.append("--host={}".format(args.host))
        if args.port:
            cmd.append("--port={}".format(args.port))
        subprocess.call(cmd, env=my_env)
    except ImportError:
        print("You must execute this command inside the project folder!")
        raise
        

def ref(args):
    """ Get BibTeX for varname """
    try:
        sys.path.append(os.getcwd())

        import database
        from .operations import work_by_varname, work_to_bibtex, reload
        reload()
        work = work_by_varname(args.varname)
        if work:
            print(work_to_bibtex(work))

    except ImportError:
        print("You must execute this command inside the project folder!")
        raise


def plugin(args):
    """ Create a chrome plugin folder """
    print("Creating {}".format(args.dir))
    recursive_copy("extension", args.dir)
    print("Done!")


def main():
    """ Entry point """
    parser = argparse.ArgumentParser(description="Snowballing tools")
    subparsers = parser.add_subparsers()
    start_parser = subparsers.add_parser(
        "start", help="start a new literature snowballing")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("path", type=str, default="literature", nargs="?")
    start_parser.add_argument("-p", "--profile", type=str, default="default")

    search_parser = subparsers.add_parser(
        "search", help="search references in the database")
    search_parser.set_defaults(func=search)
    search_parser.add_argument("query", type=str)

    ref_parser = subparsers.add_parser(
        "ref", help="get BibTeX for varname")
    ref_parser.set_defaults(func=ref)
    ref_parser.add_argument("varname", type=str)

    web_parser = subparsers.add_parser(
        "web", help="start web server")
    web_parser.set_defaults(func=web)
    web_parser.add_argument("-H", "--host", type=str, default=None)
    web_parser.add_argument("-p", "--port", type=str, default=None)

    plugin_parser = subparsers.add_parser(
        "plugin", help="export plugin")
    plugin_parser.set_defaults(func=plugin)
    plugin_parser.add_argument("-d", "--dir", type=str, default="johnsnow_plugin")

    args = parser.parse_args()
    args.func(args)
