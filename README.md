# Nb-Mypy

`Nb-Mypy` is a facility to automatically run `mypy` on Jupyter notebook cells as they are executed.


## Installation

* Download the [`nb-mypy.py`](nb-mypy.py) script and move it into your IPython profile's startup directory.

  The IPython directory can be found by running `ipython locate` in a terminal.
  Within this directory, the default profile's startup directory is `profile_default/startup/`.
  
  For example, on Linux the script could exist on a path like this:
```shell script
/yourhomedir/.ipython/profile_default/startup/nb-mypy.py
```

* This script relies on `mypy` and `astor`.
  So, make sure to have them installed. E.g.

```shell script
$ pip3 install mypy astor
```
Once installed, the `%nb_mypy` line magic becomes available in Jupyter notebooks using the IPython kernel.
You will need to restart your kernel after installing or updating `nb-mypy.py`.
At startup, automatic type checking is _disabled_.

> If you want it to be _enabled_ at startup, then make the following change in `nb-mypy.py`.
> Change `__Nb_Mypy_TypeChecker = __MypyIPython(False)` into
> `__Nb_Mypy_TypeChecker = __MypyIPython(True)`.

## Usage

In Jupyter notebooks where you want to apply
automatic type checking,
you can enable type checking by executing
(in a code cell) the line magic `%nb_mypy On`.

A robust way of attempting to enable type checking is
```python
if 'nb_mypy' in get_ipython().magics_manager.magics.get('line'):
    %nb_mypy On
```
Here are the ways to use the line magic `%nb_mypy`
* `%nb_mypy -v`: show version
* `%nb_mypy`: show the current state
* `%nb_mypy On`: enable automatic type checking
* `%nb_mypy Off`: disable automatic type checking
* `%nb_mypy DebugOn`: enable debug mode
* `%nb_mypy DebugOff`: disable debug mode


## Examples

For examples, see the Jupyter notebook [`Nb-Mypy.ipynb`](Nb-Mypy.ipynb).
