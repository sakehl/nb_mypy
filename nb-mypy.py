#! /usr/bin python3
# -*- coding:utf-8 -*-
"""
Add Mypy type-checking to jupyter/ipython, which respects history.
Save this script to your ipython profile's startup directory
and the Jupyter/IPython kernel will automatically do type checking.

The IPython profile directory can be found via `ipython locate`.
For example, this file could exist on a path like this on linux:
/home/yourusername/.ipython/profile_default/startup/nb_mypy.py

Current version was inspired by github user BradyHu
https://gist.github.com/BradyHu/f4dc997d4b53f9b23e1120940fb8f0d1
"""

__version__ = '2020.5.9'

import ast
import re
from IPython import get_ipython
from IPython.core.magic import register_line_magic
import logging
from typing import Set

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# List names in names objects, or tuples.
# The only two options which can be assigned to.
# Thus to be used in an assignment.
class Names(ast.NodeVisitor):
    """Gather the names of variables of Names and Tuple nodes.

    Specifically do not gather names from Attribute or Subscripts
    (which are also possible as an assign target).
    """

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

    If replace is True, it will also gather assigned variables which have
    subscripts or attributes.
    """

    def __init__(self, replace: bool = False):
        self.var_names = set()
        self.annotated_names = set()
        self.classfunc_names = set()
        self.replace = replace

    def visit_FunctionDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_AsyncFunctionDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_ClassDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_Assign(self, node):
        namer = Names(self.replace)
        for t in node.targets:
            namer.visit(t)
        self.var_names.update(namer.names)

    def visit_AnnAssign(self, node):
        namer = Names(self.replace)
        namer.visit(node.target)
        self.annotated_names.update(namer.names)

    def visit_AugAssign(self, node):
        namer = Names(self.replace)
        namer.visit(node.target)
        self.var_names.update(namer.names)


class Replacer(ast.NodeTransformer):
    """Replace all functions, classes and variable declarations
       with a Pass node, which are present in a list of names.
       """

    def __init__(self, known_vars: Set[str], known_annotated: Set[str], known_classfunc: Set[str]):
        """Initialize the Replacer.

        known -- The set of names which should be replaced.
        """
        self.known_vars = known_vars
        self.known_annotated = known_annotated
        self.known_classfunc = known_classfunc

    def visit_FunctionDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()
        else:
            # Remove the body of the function, we don't have to type check it anymore
            node.body = [ast.Pass()]
            return node

    def visit_AsyncFunctionDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()
        else:
            node.body = [ast.Pass()]
            return node

    def visit_ClassDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()
        else:
            return node

    def visit_Assign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.var_names:
            if n in self.known_vars:
                return ast.Pass()
        return node

    def visit_AugAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.var_names:
            if n in self.known_vars:
                return ast.Pass()
        return node

    def visit_AnnAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for n in mynames.annotated_names:
            if n in self.known_annotated:
                return ast.Pass()
        return node

    def visit_Module(self, node):
        """Remove all top level expressions and `pass`es,
        thus cleaning up the AST of unnecessary history.
        """
        res = []
        for n in node.body:
            if not (isinstance(n, ast.Pass)
                    or isinstance(n, ast.Expr)
                    ):
                res.append(n)
        node.body = res
        return ast.NodeTransformer.generic_visit(self, node)


class __MypyIPython:
    """A type checker for IPython, that uses Mypy.
    """

    def __init__(self, mypy_typecheck):
        self.mypy_cells: str = "from IPython.core.getipython import get_ipython\n"
        self.mypy_var_names = set()
        self.mypy_annotated_names = set()
        self.mypy_classfunc_names = set()
        mypy_shell = get_ipython()
        mypy_tmp_func = mypy_shell.run_cell
        self.mypy_typecheck = mypy_typecheck
        self.debug = False

        def first_none_whitspace(s: str) -> int:
            """Get the index of the first non-whitespace char.
            """
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

        def fixLineNr(s: str, offset: int) -> str:
            compiled = re.compile('(.*)(line\\s)([0-9]+)(.*)').findall(s)
            if(len(compiled) == 0):
                return s
            begin, line, nr, end = compiled[0]
            begin = fixLineNr(begin, offset)
            end = fixLineNr(end, offset)
            nr = int(nr) - offset

            return begin + line + str(nr) + end

        def mypy_tmp(cell, *args, **kwargs):
            """Function that applies type checking, and afterwards
            calls the normal function of the cell.
            """
            result = mypy_tmp_func(cell, *args, **kwargs)
            if self.mypy_typecheck:
                syntaxError = False

                try:
                    from mypy import api
                    import astor
                    from IPython.core.interactiveshell import ExecutionResult
                    import functools

                    # If we are cell magic, we don't have to type check
                    if cell.startswith("%%"):
                        return result

                    # Filter ipython related stuff
                    # We just comment it, since we still need the line numbers to match
                    cell_filter = functools.reduce(lambda a, b: a + "\n" + b,
                                                   map(commentMagic, cell.split('\n')))
                    cell_p = None
                    try:
                        cell_p = ast.parse(cell_filter)
                    except SyntaxError:
                        syntaxError = True

                    if syntaxError:
                        return result

                    getCell = NamesLister()
                    getCell.visit(cell_p)

                    new_var = getCell.var_names
                    new_annotated = getCell.annotated_names
                    new_classfunc = getCell.classfunc_names

                    # Remove if there is a new (annotated) variable or a new function
                    remove_var = (new_var | new_annotated |
                                  new_classfunc) & self.mypy_var_names
                    # Remove if there is a new annotatted variable or a new function
                    remove_annotated = (
                        new_annotated | new_classfunc) & self.mypy_annotated_names
                    # Remove a function, if any of the three is introduced with the same name
                    remove_classfunc = (
                        new_var | new_annotated | new_classfunc) & self.mypy_classfunc_names

                    if len(remove_var) or len(remove_annotated) or len(remove_classfunc):
                        try:
                            mypy_cells_ast = ast.parse(self.mypy_cells)
                        except SyntaxError:
                            if self.debug:
                                logger.debug(self.mypy_cells)
                            return result
                        new_mypy_cells_ast = Replacer(
                            remove_var, remove_annotated, remove_classfunc).visit(mypy_cells_ast)
                        self.mypy_cells = astor.to_source(new_mypy_cells_ast)
                    # First remove the removed things from the sets, since it could changed from function to variable
                    # or visa-versa
                    self.mypy_var_names.difference_update(remove_var)
                    self.mypy_var_names.update(new_var)
                    self.mypy_annotated_names.difference_update(
                        remove_annotated)
                    self.mypy_annotated_names.update(new_annotated)
                    self.mypy_classfunc_names.difference_update(
                        remove_classfunc)
                    self.mypy_classfunc_names.update(new_classfunc)

                    mypy_cells_length = len(self.mypy_cells.split('\n'))-1
                    self.mypy_cells += (cell_filter + '\n')
                    if self.debug:
                        logger.debug(self.mypy_cells)

                    mypy_result = api.run(
                        ['--ignore-missing-imports', '--allow-redefinition', '-c', self.mypy_cells])
                    if mypy_result[0]:
                        for line in mypy_result[0].strip().split('\n'):
                            compiled = re.compile(
                                '(<[a-z]+>:)(\\d+)(.*?)$').findall(line)
                            if len(compiled) > 0:
                                _, n, r = compiled[0]
                                if int(n) > mypy_cells_length:
                                    n = str(int(n)-mypy_cells_length)
                                    r = fixLineNr(r, mypy_cells_length)
                                    logger.info("".join(["<cell>", n, r]))

                    if mypy_result[1]:
                        logger.error(mypy_result[1])

                except Exception:
                    logger.critical(
                        "Error in type checker, you can turn it off with '%nb_mypy Off'")
                    if self.debug:
                        logger.exception("Fatal error: please report")

            return result

        mypy_shell.run_cell = mypy_tmp

    def state(self):
        """Show current state.
        """
        on_off = {True: 'On', False: 'Off'}
        debug_on_off = {True: 'DebugOn', False: 'DebugOff'}
        logger.info(f"nb_mypy state: {on_off[self.mypy_typecheck]} {debug_on_off[self.debug]}")

    def stop(self):
        """Disable automatic type checking.
        """
        self.mypy_typecheck = False

    def start(self):
        """Enable automatic type checking.
        """
        self.mypy_typecheck = True

    def debug_on(self):
        """Enable debug mode.
        """
        self.debug = True

    def debug_off(self):
        """Disable debug mode.
        """
        self.debug = False


__Nb_Mypy_TypeChecker = __MypyIPython(False)


@register_line_magic
def nb_mypy(line):
    """Inspect or modify mypy autochecking state.
    """
    switcher = {
        '': __Nb_Mypy_TypeChecker.state,
        'On': __Nb_Mypy_TypeChecker.start,
        'Off': __Nb_Mypy_TypeChecker.stop,
        'DebugOn': __Nb_Mypy_TypeChecker.debug_on,
        'DebugOff': __Nb_Mypy_TypeChecker.debug_off,
    }
    # logger.info(f"line magic argument: {line!r}")

    def unknown():
        logger.error(f"nb_mypy: Unknown argument\nValid arguments: {list(switcher.keys())!r}")

    switcher.get(line, unknown)()


logger.info(f"nb-mypy.py version {__version__}")
