# coding: utf-8

import sys
from setuptools import setup, find_packages

NAME = "isilon_sdk"
VERSION = "1.0.0"



# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = ["urllib3 >= 1.15"]

setup(
    name=NAME,
    version=VERSION,
    description="Isilon SDK",
    author_email="sdk@isilon.com",
    url="http://www.emc.com",
    keywords=["Swagger", "Isilon SDK"],
    install_requires=REQUIRES,
    packages=[NAME],
    long_description="""\
    Isilon SDK - Tools for Swagger Open API Specification for OneFS API
    """
)
