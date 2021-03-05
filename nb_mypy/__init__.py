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

__version__ = '1.0.0'

import ast
import functools
import logging
import re
from typing import Set, Optional

import astor  # type: ignore
from mypy import api
import IPython  # type: ignore
from IPython.core.magic import register_line_magic  # type: ignore

# List names in names objects, or tuples.
#


class Names(ast.NodeVisitor):
    """Gather the names of variables of Names and Tuple nodes,
    the only two options which can be assigned to.

    Only gather names from Attribute or Subscripts (which are
    also possible as an assign target) if replace is True.
    """

    def __init__(self, replace=False):
        self.names = set()
        self.replace = replace

    def visit_Name(self, node):
        self.names.add(str(node.id))

    # Unsure why this was here again, maybe remove?
    def visit_Tuple(self, node):
        for e in node.elts:
            self.visit(e)

    def visit_Attribute(self, node):
        if self.replace:
            self.visit(node.value)

    def visit_Subscript(self, node):
        if self.replace:
            self.visit(node.value)


class NamesLister(ast.NodeVisitor):
    """Gather the names of all assigned variables, classes and functions.

    If replace is True, it will also gather assigned variables which have
    subscripts or attributes.
    """

    def __init__(self, replace: bool = False):
        self.var_names: Set[str] = set()
        self.annotated_names: Set[str] = set()
        self.classfunc_names: Set[str] = set()
        self.replace = replace

    def visit_FunctionDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_AsyncFunctionDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_ClassDef(self, node):
        self.classfunc_names.add(node.name)

    def visit_Assign(self, node):
        namer = Names(self.replace)
        for target in node.targets:
            namer.visit(target)
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

        known_vars, known_annotated, known_classfunc-- The set of names which should be replaced.
        """
        self.known_vars = known_vars
        self.known_annotated = known_annotated
        self.known_classfunc = known_classfunc

    def visit_FunctionDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()

        # Remove the body of the function, we don't have to type check it anymore
        node.body = [ast.Pass()]
        return node

    def visit_AsyncFunctionDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()

        node.body = [ast.Pass()]
        return node

    def visit_ClassDef(self, node):
        if node.name in self.known_classfunc:
            return ast.Pass()

        return node

    def visit_Assign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for name in mynames.var_names:
            if name in self.known_vars:
                return ast.Pass()
        return node

    def visit_AugAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for name in mynames.var_names:
            if name in self.known_vars:
                return ast.Pass()
        return node

    def visit_AnnAssign(self, node):
        mynames = NamesLister(True)
        mynames.visit(node)
        for name in mynames.annotated_names:
            if name in self.known_annotated:
                return ast.Pass()
        return node

    def visit_Module(self, node):
        """Remove all top level expressions and `pass`es,
        thus cleaning up the AST of unnecessary history.
        """
        res = []
        for statement in node.body:
            if not isinstance(statement, (ast.Pass, ast.Expr)):
                res.append(statement)
        node.body = res
        return ast.NodeTransformer.generic_visit(self, node)


def first_none_whitspace(line: str) -> int:
    """Get the index of the first non-whitespace char.
    """
    i = 0

    for char in line:
        if char.isspace():
            i += 1
        else:
            break

    return i


def comment_magic(line: str) -> str:
    """Comments out specific iPython things,
    which are not valid python, such as line magic,
    help and shell escapes.
    """
    i = first_none_whitspace(line)

    if i >= len(line):
        return line
    fst = line[i]
    lst = line[-1]
    if fst in "%!?" or lst in "?":
        return line[:i] + "pass #" + line[i:]

    return line


def fix_line_nr(line: str, offset: int) -> str:
    """Change the line numbering in the line, with regards to the offset.
    """
    compiled = re.compile('(.*)(line\\s)([0-9]+)(.*)').findall(line)
    if len(compiled) == 0:
        return line
    begin, line, number, end = compiled[0]
    begin = fix_line_nr(begin, offset)
    end = fix_line_nr(end, offset)
    number = int(number) - offset

    return begin + line + str(number) + end


class MypyIPython:
    """A type checker for IPython, that uses Mypy.
    """

    def __init__(self) -> None:
        self.mypy_cells: str = "from IPython import get_ipython\n"
        self.mypy_var_names: Set[str] = set()
        self.mypy_annotated_names: Set[str] = set()
        self.mypy_classfunc_names: Set[str] = set()

        self.mypy_typecheck: bool = True
        self.debug: bool = False

        self.logger = logging.getLogger('nb-mypy')
        self.logger.setLevel(logging.DEBUG)
        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.stream_handler)

    def type_check(self, info: IPython.core.interactiveshell.ExecutionInfo) -> None:
        """Type check an info cell
        """
        if self.mypy_typecheck:
            self.type_check_cell(info.raw_cell)

    def type_check_cell(self, cell: str) -> None:
        """Function that applies type checking on the cell string
        """
        try:
            # If we are cell magic, we don't have to type check
            if cell.startswith("%%"):
                return

            # Filter ipython related stuff
            # We just comment it, since we still need the line numbers to match
            cell_filter = functools.reduce(lambda a, b: a + "\n" + b,
                                           map(comment_magic, cell.split('\n')))
            cell_p = None
            try:
                cell_p = ast.parse(cell_filter)
            except SyntaxError:
                if self.debug:
                    self.logger.debug(
                        "Syntax error in cell:\n%s", cell_filter)
                return

            get_cell_names = NamesLister()
            get_cell_names.visit(cell_p)

            self.clean_history(get_cell_names.var_names,
                               get_cell_names.annotated_names,
                               get_cell_names.classfunc_names)

            mypy_cells_length = len(self.mypy_cells.split('\n'))-1
            self.mypy_cells += (cell_filter + '\n')

            if self.debug:
                self.logger.debug(
                    "Program before typechecking:\n%s", self.mypy_cells)

            mypy_result = api.run(
                ['--ignore-missing-imports', '--allow-redefinition', '-c', self.mypy_cells])

            if mypy_result[0]:
                for line in mypy_result[0].strip().split('\n'):
                    compiled = re.compile(
                        '(<[a-z]+>:)(\\d+)(.*?)$').findall(line)

                    if compiled:
                        _, line_nr, message = compiled[0]
                        if int(line_nr) > mypy_cells_length:
                            line_nr = str(int(line_nr)-mypy_cells_length)
                            message = fix_line_nr(message, mypy_cells_length)
                            self.logger.error(
                                "".join(["<cell>", line_nr, message]))

            if mypy_result[1]:
                self.logger.error(mypy_result[1])

            if self.debug:
                self.logger.debug("Finished type checking")

        except Exception as excep:
            self.logger.critical(
                "Error in type checker, you can turn it off with '%nb_mypy Off'")
            if self.debug:
                self.logger.debug(
                    "Error was fatal: please report it\n%s", excep)

    def clean_history(self, new_var, new_annotated, new_classfunc) -> None:
        """Clean the history of any re-definitions of variables, classes or functions."""
        # Remove if there is a new (annotated) variable or a new function
        remove_var = (new_var | new_annotated |
                      new_classfunc) & self.mypy_var_names
        # Remove if there is a new annotatted variable or a new function
        remove_annotated = (
            new_annotated | new_classfunc) & self.mypy_annotated_names
        # Remove a function, if any of the three is introduced with the same name
        remove_classfunc = (
            new_var | new_annotated | new_classfunc) & self.mypy_classfunc_names

        if remove_var or remove_annotated or remove_classfunc:
            try:
                mypy_cells_ast = ast.parse(self.mypy_cells)
            except SyntaxError:
                if self.debug:
                    self.logger.error(
                        "Syntax error in old cells:\n%s", self.mypy_cells)
                else:
                    self.logger.error("Syntax error in old cells")
                return
            new_mypy_cells_ast = Replacer(
                remove_var, remove_annotated, remove_classfunc).visit(mypy_cells_ast)
            self.mypy_cells = astor.to_source(new_mypy_cells_ast)

        # First remove the removed things from the sets, since it could change from
        # function to variable or visa-versa
        self.mypy_var_names.difference_update(remove_var)
        self.mypy_var_names.update(new_var)
        self.mypy_annotated_names.difference_update(
            remove_annotated)
        self.mypy_annotated_names.update(new_annotated)
        self.mypy_classfunc_names.difference_update(
            remove_classfunc)
        self.mypy_classfunc_names.update(new_classfunc)

    def version(self):
        """Show version.
        """
        self.logger.info("Version %s", __version__)

    def state(self):
        """Show current state.
        """
        on_off = {True: 'On', False: 'Off'}
        debug_on_off = {True: 'DebugOn', False: 'DebugOff'}
        self.logger.info(
            "State: %s %s", on_off[self.mypy_typecheck], debug_on_off[self.debug])

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


__NB_TYPECHECKER: Optional[MypyIPython] = None


def load_ipython_extension(ipython_shell: IPython.core.interactiveshell.InteractiveShell):
    """Load the nb-mypy extension."""

    global __NB_TYPECHECKER
    __NB_TYPECHECKER = MypyIPython()
    __NB_TYPECHECKER.version()
    ipython_shell.events.register(
        'pre_run_cell', __NB_TYPECHECKER.type_check)

    @register_line_magic
    def nb_mypy(line):
        """Inspect or modify mypy autochecking state.
        """
        global __NB_TYPECHECKER
        switcher = {
            '': __NB_TYPECHECKER.state,
            '-v': __NB_TYPECHECKER.version,
            'On': __NB_TYPECHECKER.start,
            'Off': __NB_TYPECHECKER.stop,
            'DebugOn': __NB_TYPECHECKER.debug_on,
            'DebugOff': __NB_TYPECHECKER.debug_off,
        }

        def unknown():
            __NB_TYPECHECKER.logger.error(
                "Unknown argument\n Valid arguments: %s", list(switcher.keys()))

        switcher.get(line, unknown)()


def unload_ipython_extension(ipython_shell: IPython.core.interactiveshell.InteractiveShell):
    """Unload the nb-mypy extension."""
    global __NB_TYPECHECKER
    if __NB_TYPECHECKER is not None:
        ipython_shell.events.unregister(
            'pre_run_cell', __NB_TYPECHECKER.type_check)
        __NB_TYPECHECKER.logger.removeHandler(__NB_TYPECHECKER.stream_handler)
