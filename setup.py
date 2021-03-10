from setuptools import setup
import re


def get_property(prop, file):
    result = re.search(
        r'{}\s*=\s*[\'"]([^\'"]*)[\'"]'.format(prop), open(file).read())
    return result.group(1)


setup(
    version=get_property('__version__', 'nb_mypy/version.py')
)
