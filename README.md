# Nb Mypy

_Nb Mypy_ is a facility to automatically run `mypy`[http://mypy-lang.org/] on Jupyter notebook cells as they are executed, whilst retaining information about the execution history.


## Installation

* _Nb Mypy_ relies on the packages mypy and astor, which you can install like this:
```bash
python3 -m pip install mypy astor
```
* _Nb Mypy_ can be installed like:
```bash
python3 -m pip install nb_mypy
```

Once installed, you can load it via `%load_ext nb_mypy` in a cell of  a Jupyter notebook using the IPython kernel.

### Installation from source
The package is build via PyPA's `build`, make sure you have the latest available via 
```bash
python3 -m pip install --upgrade build
```


You can then build the package from the current directory where `pyproject.toml` is located:
```bash
python3 -m build
```

Now you can install it using 
```bash
python3 -m pip install --no-index --find-links=./dist nb_mypy
```

## Usage

In Jupyter notebooks where you want to apply
automatic type checking,
you can load this extension to do type checking by executing
(in a code cell) the line magic `%load_ext nb_mypy`.

With the line magic `%nb_mypy` you can modify the behaviour of _Nb Mypy_

Here are the ways to use the line magic `%nb_mypy`
* `%nb_mypy -v`: show version
* `%nb_mypy`: show the current state
* `%nb_mypy On`: enable automatic type checking
* `%nb_mypy Off`: disable automatic type checking
* `%nb_mypy DebugOn`: enable debug mode
* `%nb_mypy DebugOff`: disable debug mode


## Examples

For examples, see the Jupyter notebook [`Nb_Mypy.ipynb`](Nb_Mypy.ipynb).
