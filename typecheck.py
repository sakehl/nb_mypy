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

import functools
import re
import sys
import traceback

import astor
import ast
from IPython import get_ipython

class NamesLister(ast.NodeVisitor):
    def __init__(self):
        self.names = []
    
    def visit_FunctionDef(self, node):
        self.names.append(node.name)
        
    def visit_AsyncFunctionDef(self, node):
        self.names.append(node.name)
    
    def visit_ClassDef(self, node):
        self.names.append(node.name)
        
    def visit_Name(self, node):
        self.names.append(str(node.id))
        
    def visit_Assign(self, node):
        for t in node.targets:
            self.visit(t)

    def visit_AnnAssign(self, node):
        self.visit(node.target)
    
    def visit_AugAssign(self, node):
        self.visit(node.target)

    def visit_Expr(self, node):
        return
        
        
class Remover(ast.NodeTransformer):
    def __init__(self, known):
        self.known = known
        
    def visit_FunctionDef(self, node):
        if node.name in self.known:
            return None
        else:
            return node
        
    def visit_AsyncFunctionDef(self, node):
        if node.name in self.known:
            return None
        else:
            return node
    
    def visit_ClassDef(self, node):
        if node.name in self.known:
            return None
        else:
            return node
   
    def visit_Assign(self, node):
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return None
        return node
    
    def visit_AnnAssign(self, node):
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return None
        return node
    
    def visit_AugAssign(self, node):
        mynames = NamesLister()
        mynames.visit(node)
        for n in mynames.names:
            if n in self.known:
                return None
        return node

def commentMagic(s: str) -> str:
    news = s.lstrip()
    if(len(news) == 0):
         return s
    
    if(news[0] == '%' or news[0] == '!'):
         return "# " + s
    return s

mypy_cells = ''
mypy_names = set()
mypy_shell = get_ipython()
mypy_tmp_func = mypy_shell.run_cell
mypy_typecheck=True
def mypy_tmp(cell,*args,**kwargs):
    if mypy_typecheck:
        from mypy import api

        global mypy_cells
        global mypy_names
        # Filter bash escapes (!) and magics (%)
        # We just comment it, since we still need the line numbers to match
        cell_lines = cell.split('\n')
        cell_filter = functools.reduce(lambda a,b : a + "\n" + b,
                                map(commentMagic, cell.split('\n')))
        cell_p = None
        try:
            cell_p = ast.parse(cell_filter)
        except SyntaxError as e:
            _, ex, tb = sys.exc_info()
            traceback.print_exc(0)
            return IPython.core.interactiveshell.ExecutionResult(e)
        
        getCell = NamesLister()
        getCell.visit(cell_p)
        newnames = set(getCell.names)
        remove = newnames & mypy_names
        if(len(remove) > 0):
            mypy_cells_ast = ast.parse(mypy_cells)
            new_mypy_cells_ast = Remover(remove).visit(mypy_cells_ast)
            mypy_cells = astor.to_source(new_mypy_cells_ast)

        mypy_names = mypy_names | newnames
        
        mypy_cells_length = len(mypy_cells.split('\n'))-1
        mypy_cells+=(cell_filter +'\n')
        mypy_result = api.run(['--ignore-missing-imports','--allow-redefinition','-c', mypy_cells])
        if mypy_result[0]:
            for line in mypy_result[0].strip().split('\n'):
                compiled = re.compile('(<[a-z]+>:)(\d+)(.*?)$').findall(line)
                if len(compiled) > 0:
                    l,n,r = compiled[0]
                    if("already defined" in r):
                        print(r)
                        continue
                    if int(n)>mypy_cells_length:
                        n = str(int(n)-mypy_cells_length)
                        print("".join(["<cell>",n,r]))

        if mypy_result[1]:
            print(mypy_result[1])
    return mypy_tmp_func(cell,*args,**kwargs)
mypy_shell.run_cell = mypy_tmp
