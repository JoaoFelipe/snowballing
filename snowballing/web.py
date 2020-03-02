import os
import sys 
import importlib
import io
import traceback
from functools import wraps
from contextlib import redirect_stdout, redirect_stderr

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from .collection_helpers import oget, dset
from .utils import parse_bibtex
from .snowballing import form_definition, WebNavigator
from .operations import bibtex_to_info, load_work_map_all_years
from .operations import work_to_bibtex, reload, find, work_by_varname
from .operations import should_add_info
from .operations import invoke_editor, metakey
from .dbmanager import insert, set_attribute
from . import config

if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

import database


app = Flask(__name__)
CORS(app)

LOADED_DB = False
STATUS = set()

def load_db():
    global LOADED_DB
    importlib.reload(database)    
    reload()
    LOADED_DB = True


def find_work_by_scholar_id(scholar_id):
    if not LOADED_DB:
        load_db()
    
    for varname, work in load_work_map_all_years():
        config.check_load(work, varname, warning=lambda x: STATUS.add(x))
        if oget(work, "scholar_id", "", cvar=config.SCHOLAR_MAP) == scholar_id:
            return work
    return None


def latex_to_info(latex):
    if latex is not None:
        entries = parse_bibtex(latex)
        try:
            info = bibtex_to_info(entries[0], config.BIBTEX_TO_INFO_WITH_TYPE)
            return info
        except:
            return None


def unified_find(info, scholar, latex, db_latex, citation_var, citation_file, backward):
    try:       
        citation_work = work_by_varname(citation_var)
        if citation_var and not citation_work:
            STATUS.add("[Error] Citation var {} not found".format(citation_var))

        work = None
        db_latex = None
        if latex is not None:
            info = latex_to_info(latex)
        if info is None and db_latex is not None:
            info = latex_to_info(db_latex)

        work = find_work_by_scholar_id(scholar["scholar_id"])
        if work is not None and info is None:
            info = latex_to_info(work_to_bibtex(work))

        if info is not None:
            for key, value in scholar.items():
                if value is not None:
                    info[config.SCHOLAR_MAP.get(key, key)] = value
            
            should, work, info = should_add_info(
                info, citation_work, article=None,
                backward=backward, citation_file=citation_file,
                warning=lambda x: STATUS.add("[Warning]" + x),
                add_citation=bool(citation_var),
                bibtex_rules=config.BIBTEX_TO_INFO_IGNORE_SET_ID
            )

            if work is not None:
                dset(info, "pyref", work @ metakey)
            
        else:
            should = {
                "add": True,
                "citation": citation_work,
                "set": {},
                "backward": backward
            }
        
        if work:
            if not db_latex:
                db_latex = work_to_bibtex(work)
            if not latex:
                latex = db_latex

        
        return {
            "result": "ok",
            "msg": "",
            "found": bool(work),
            "info": info,
            "latex": latex,
            "db_latex": db_latex,
            "citation": bool(should["citation"]),
            "add": should["add"],
            "status": list(STATUS),
        }, work, should
    except Exception as e:
        traceback.print_exc()
        return {
            "result": "error",
            "msg": repr(e),
            "status": list(STATUS),
        }, None, None


def unified_exc(message, reload=False):
    def unified_dec(func):
        @wraps(func)
        def dec():
            try:
                if reload:
                    load_db()
                    importlib.reload(database)
                result, work, should_add = unified_find(
                    request.json.get('info'),
                    {
                        "scholar_id": request.json.get('scholar_id'),
                        "cluster_id": request.json.get('cluster_id'),
                        "scholar": request.json.get('scholar'),
                        "scholar_ok": request.json.get('scholar_ok'),
                    },
                    request.json.get('latex'),
                    request.json.get('db_latex'),
                    request.json.get('citation_var'),
                    request.json.get('citation_file'),
                    request.json.get('backward'),
                )
                result = func(result, work, should_add)
            except Exception as e:
                result['msg'] = message + ': ' + repr(e)
                traceback.print_exc()
            if result['msg']:
                result['result'] = 'error'
            return jsonify(result)
        return dec
    return unified_dec


@app.route('/')
def root():
    return render_template('hello.html')

@app.route('/ping', methods=['GET', 'POST'])
def ping():
    return {
        "result": "ok",
        "msg": "",
    }


@app.route('/find', methods=['GET', 'POST'])
@unified_exc('Unable to find work')
def find_work(result, work, should_add):
    return result


@app.route('/click', methods=['GET', 'POST'])
@unified_exc('Unable to open editor')
def do_click(result, work, should_add):
    if work:
        invoke_editor(work)
    else:
        result["msg"] = "Work not found"
    return result


@app.route('/form', methods=['GET', 'POST'])
@unified_exc('Unable to load form', reload=True)
def form(result, work, should_add):
    result["form"] = form_definition()
    return result

@app.route('/form/submit', methods=['GET', 'POST'])
@unified_exc('Unable to submit form', reload=True)
def submit_form(result, work, should_add):
    if result["result"] == "ok":
        info = result["info"]
        backward = request.json.get('backward') or ""
        values = request.json.get('values')
        citation_var = request.json.get('citation_var')
        citation_file = request.json.get('citation_file')
        navigator = WebNavigator(
            values, work, info,
            citation_file=citation_file,
            citation_var=citation_var,
            backward=backward,
            should_add=should_add,
        )
        result["form"] = form_definition()
        result["resp"] = navigator.show()
    return result

@app.route('/run', methods=['GET', 'POST'])
def run():
    try:
        error = False
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                exec(request.json.get('code'))
            except:
                traceback.print_exc()
                error = True
        return jsonify({
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
            "error": error,
            "result": "ok",
            "msg": "",
            "status": list(STATUS),
        })
    except Exception as e:
        return jsonify({
            "result": "error",
            "msg": "Unable to run code: " + repr(e),
            "status": list(STATUS),
        })


@app.route('/clear', methods=['GET', 'POST'])
def clear():
    load_db()
    STATUS.clear()
    return jsonify({
        'result': 'ok',
        'msg': '',
        'status': list(STATUS),
    })




if __name__ == '__main__':
    app.run()