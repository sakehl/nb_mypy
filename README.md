# Nb Mypy

_Nb Mypy_ is a facility to automatically run [`mypy`](http://mypy-lang.org/) on Jupyter notebook cells as they are executed, whilst retaining information about the execution history.


## Installation

* _Nb Mypy_ relies on the packages mypy and astor, but those should be automatically installed.
* _Nb Mypy_ can be installed like:
```bash
python3 -m pip install nb_mypy
```

Once installed, you can load it via `%load_ext nb_mypy` in a cell of  a Jupyter notebook using the IPython kernel.

### Installation from source
The package can also be installed from source, using pip:
```bash
pip3 install .
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
* `%nb_mypy mypy-options` [OPTIONS]: Provide extra options to mypy (for example --strict)


## Examples

For examples, see the Jupyter notebook [`Nb_Mypy.ipynb`](https://gitlab.tue.nl/jupyter-projects/nb_mypy/-/blob/master/Nb_Mypy.ipynb).
