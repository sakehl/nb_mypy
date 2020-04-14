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

import ast
from IPython import get_ipython
from IPython.core.magic import register_line_magic

# List names in names objects, or tuples.
# The only two options which can be assigned to
# Thus to be used in an assignmed
class Names(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        self.names.add(str(node.id))

    def visit_Tuple(self, node):
        for e in node.elts:
            self.visit(e)

class NamesLister(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_FunctionDef(self, node):
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node):
        self.names.add(node.name)

    def visit_ClassDef(self, node):
        self.names.add(node.name)

    def visit_Assign(self, node):
        namer = Names()
        for t in node.targets:
            namer.visit(t)
        self.names.update(namer.names)

    def visit_AnnAssign(self, node):
        namer = Names()
        namer.visit(node.target)
        self.names.update(namer.names)

    def visit_AugAssign(self, node):
        namer = Names()
        namer.visit(node.target)
        self.names.update(namer.names)


class Remover(ast.NodeTransformer):
    def __init__(self, known):
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
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node

    def visit_AnnAssign(self, node):
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node

    def visit_AugAssign(self, node):
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return ast.Pass()
        return node


class __MyPyIPython:
    def __init__(self):
        self.mypy_cells = ""
        self.mypy_names = set()
        mypy_shell = get_ipython()
        mypy_tmp_func = mypy_shell.run_cell
        self.mypy_typecheck = True
        self.debug = False

        def commentMagic(s: str) -> str:
            news = s.lstrip()
            if(len(news) == 0):
                return s

            if(news[0] == '%' or news[0] == '!'):
                return "# " + s
            return s

        def mypy_tmp(cell, *args, **kwargs):
            if self.mypy_typecheck:
                try:
                    from mypy import api
                    import functools
                    import re
                    import sys
                    import traceback
                    import astor
                    from IPython.core.interactiveshell import ExecutionResult


                    # Filter bash escapes (!) and magics (%)
                    # We just comment it, since we still need the line numbers to match
                    cell_lines = cell.split('\n')
                    cell_filter = functools.reduce(lambda a, b: a + "\n" + b,
                                                map(commentMagic, cell.split('\n')))
                    cell_p = None
                    try:
                        cell_p = ast.parse(cell_filter)
                    except SyntaxError as e:
                        _, ex, tb = sys.exc_info()
                        traceback.print_exc(0)
                        return ExecutionResult(e)

                    getCell = NamesLister()
                    getCell.visit(cell_p)
                    newnames = getCell.names
                    remove = newnames & self.mypy_names
                    if(len(remove) > 0):
                        try:
                            mypy_cells_ast = ast.parse(self.mypy_cells)
                            if(self.debug):
                                print(self.mypy_cells)
                        except:
                            print(self.mypy_cells)
                            return mypy_tmp_func(cell, *args, **kwargs)
                        new_mypy_cells_ast = Remover(remove).visit(mypy_cells_ast)
                        self.mypy_cells = astor.to_source(new_mypy_cells_ast)

                    self.mypy_names.update(newnames)

                    mypy_cells_length = len(self.mypy_cells.split('\n'))-1
                    self.mypy_cells += (cell_filter + '\n')
                    mypy_result = api.run(
                        ['--ignore-missing-imports', '--allow-redefinition', '-c', self.mypy_cells])
                    if mypy_result[0]:
                        for line in mypy_result[0].strip().split('\n'):
                            compiled = re.compile('(<[a-z]+>:)(\d+)(.*?)$').findall(line)
                            if len(compiled) > 0:
                                l, n, r = compiled[0]
                                if(self.debug and "already defined" in r):
                                    print(r)
                                    continue
                                if int(n) > mypy_cells_length:
                                    n = str(int(n)-mypy_cells_length)
                                    print("".join(["<cell>", n, r]))

                    if mypy_result[1]:
                        print(mypy_result[1])
                except:
                    print("Error in typechecker, you can turn it off with '%turnOffTyCheck'")
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