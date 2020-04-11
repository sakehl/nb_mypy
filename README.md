# NbMyPy

Facility to automatically run mypy on Jupyter notebook cells as they are executed.


## Installation

Save the 'typecheck.py' script to your ipython profile's startup directory and the jupyter/ipython shell will typecheck automatically.
Ipython profile directory can be found via `ipython locate [profile]`. For example, this file could exist on a path like this on linux:
```/home/yourusername/.ipython/profile_default/startup/typecheck.py```

This script relies on mypy and astor, so make sure to have them installed. E.g.

```$ pip3 install mypy astor```

## Usage

...


## Examples

...
