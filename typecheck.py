#! /usr/bin python3
# -*- coding:utf-8 -*-
"""
Add mypy type-checking to jupyter/ipython, which respects history.
Save this script to your ipython profile's startup directory
and the jupyter/ipython shell will do typecheck automatically.

Ipython profile directory can be found via `ipython locate [profile]`
For example, this file could exist on a path like this on linux:
/home/yourusername/.ipython/profile_default/startup/typecheck.py

Current version was inspired by github user BradyHu
https://gist.github.com/BradyHu/f4dc997d4b53f9b23e1120940fb8f0d1
"""

__version__ = '2020.4.1'

import ast
import re
from IPython import get_ipython
from IPython.core.magic import register_line_magic
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# List names in names objects, or tuples.
# The only two options which can be assigned to
# Thus to be used in an assignmed
class Names(ast.NodeVisitor):
    """Gather the names of variables of Names and Tuple nodes.
    Specifically do not gather names from Attribute or Subscripts
    (which are also possible as an assign target)"""
    def __init__(self, replace=False):
        self.names = set()
        self.replace = replace

    def visit_Name(self, node):
        self.names.add(str(node.id))

    def visit_Tuple(self, node):
        for e in node.elts:
            self.visit(e)

    def visit_Attribute(self, node):
        if(self.replace):
            self.visit(node.value)

    def visit_Subscript(self, node):
        if(self.replace):
            self.visit(node.value)


class NamesLister(ast.NodeVisitor):
    """Gather the names of all assigned variables, classes and functions.
    If replace is true, it will also gather assigned variables which have
    subscripts or attributes."""
    def __init__(self, replace=False):
        self.names = set()
        self.replace = replace

    def visit_FunctionDef(self, node):
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node):
        self.names.add(node.name)

    def visit_ClassDef(self, node):
        self.names.add(node.name)

    def visit_Assign(self, node):
        namer = Names(self.replace)
        for t in node.targets:
            namer.visit(t)
        self.names.update(namer.names)

    def visit_AnnAssign(self, node):
        namer = Names(self.replace)
        namer.visit(node.target)
        self.names.update(namer.names)

    def visit_AugAssign(self, node):
        namer = Names(self.replace)
        namer.visit(node.target)
        self.names.update(namer.names)


class Replacer(ast.NodeTransformer):
    """Replace all functions, classes and variable declarations
       with a Pass node, which are present in a list of names."""
    def __init__(self, known):
        """Intialize the Replacer.

        known -- The set of names which should be replaced.
        """
        self.known = known

    def visit_FunctionDef(self, node):
        if node.name in self.known:
            return ast.Pass()
        else:
            return node

    def visit_AsyncFunctionDef(self, node):
        if node.name in self.known:
            return ast.Pass()
        else:
            return node

    def visit_ClassDef(self, node):
        if node.name in self.known:
            return ast.Pass()
        else:
            return node

    def visit_Assign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node

    def visit_AnnAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node

    def visit_AugAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node


class __MyPyIPython:
    """An type checker for iPython, that uses MyPy."""

    def __init__(self):
        self.mypy_cells : str = ""
        self.mypy_names = set()
        mypy_shell = get_ipython()
        mypy_tmp_func = mypy_shell.run_cell
        self.mypy_typecheck = True
        self.debug = False

        def first_none_whitspace(s: str) -> int:
            "Get the index of the first non whitespace char."
            i = 0
            for c in s:
                if c.isspace():
                    i += 1
                else:
                    break
            
            return i


        def commentMagic(s: str) -> str:
            """Comments out specific iPython things,
            which are not valid python, such as line magic,
            help and shell escapes.
            """
            i = first_none_whitspace(s)

            if i >= len(s):
                return s
            fst = s[i]
            lst = s[-1]
            if fst in "%!?" or lst in "?":
                return s[:i] + "pass #" + s[i:]

            return s

        def fixLineNr(s : str, offset : int) -> str:
            compiled = re.compile('(.*)(line\\s)([0-9]+)(.*)').findall(s)
            if(len(compiled) == 0):
                return s
            begin,line,nr,end = compiled[0]
            begin = fixLineNr(begin, offset)
            end   = fixLineNr(end, offset)
            nr    = int(nr) - offset

            return begin + line + str(nr) + end

        def mypy_tmp(cell, *args, **kwargs):
            """Function that applies typechecking, and afterwards
            calls the normal function of the cell"""
            if self.mypy_typecheck:
                import traceback
                import functools
                import sys

                try:
                    from mypy import api
                    import astor
                    from IPython.core.interactiveshell import ExecutionResult

                    #If we are cell magic, we don't have to type check
                    if(cell.startswith("%%")):
                        return mypy_tmp_func(cell, *args, **kwargs)

                    # Filter ipython related stuff
                    # We just comment it, since we still need the line numbers to match
                    cell_filter = functools.reduce(lambda a, b: a + "\n" + b,
                                                   map(commentMagic, cell.split('\n')))
                    cell_p = None
                    try:
                        cell_p = ast.parse(cell_filter)
                    except SyntaxError as e:
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback,limit=0)
                        # logger.exception("SyntaxError")
                        return ExecutionResult(e)
                    
                    getCell = NamesLister()
                    getCell.visit(cell_p)
                    newnames = getCell.names
                    remove = newnames & self.mypy_names
                    if len(remove):
                        try:
                            mypy_cells_ast = ast.parse(self.mypy_cells)
                        except SyntaxError:
                            if self.debug:
                                logger.debug(self.mypy_cells)
                            return mypy_tmp_func(cell, *args, **kwargs)
                        new_mypy_cells_ast = Replacer(remove).visit(mypy_cells_ast)
                        self.mypy_cells = astor.to_source(new_mypy_cells_ast)

                    self.mypy_names.update(newnames)

                    mypy_cells_length = len(self.mypy_cells.split('\n'))-1
                    self.mypy_cells += (cell_filter + '\n')
                    if self.debug:
                        logger.debug(self.mypy_cells)

                    mypy_result = api.run(
                        ['--ignore-missing-imports', '--allow-redefinition', '-c', self.mypy_cells])
                    if mypy_result[0]:
                        for line in mypy_result[0].strip().split('\n'):
                            compiled = re.compile('(<[a-z]+>:)(\\d+)(.*?)$').findall(line)
                            if len(compiled) > 0:
                                l, n, r = compiled[0]
                                if int(n) > mypy_cells_length:
                                    n = str(int(n)-mypy_cells_length)
                                    r = fixLineNr(r, mypy_cells_length)
                                    logger.info("".join(["<cell>", n, r]))

                    if mypy_result[1]:
                        logger.error(mypy_result[1])

                except Exception:
                    logger.critical("Error in typechecker, you can turn it off with '%turnOffTyCheck'")
                    if self.debug:
                        logger.exception("Fatal error: please report")

            return mypy_tmp_func(cell, *args, **kwargs)

        mypy_shell.run_cell = mypy_tmp

    def stop(self):
        self.mypy_typecheck = False

    def start(self):
        self.mypy_typecheck = True

    def debugOn(self):
        self.debug = True

    def debugOff(self):
        self.debug = False

__TypeChecker = __MyPyIPython()


@register_line_magic
def turnOffTyCheck(line):
    "Turned off type checker"
    __TypeChecker.stop()


@register_line_magic
def turnOnTyCheck(line):
    "Turned on type checker"
    __TypeChecker.start()


@register_line_magic
def turnOnTyDebug(line):
    "Turned on type checker"
    __TypeChecker.debugOn()


@register_line_magic
def turnOffTyDebug(line):
    "Turned on type checker"
    __TypeChecker.debugOff()


logger.info(f"typecheck.py version {__version__}")