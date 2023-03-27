[![Build Status](https://travis-ci.org/Isilon/isilon_sdk.svg?branch=master)](https://travis-ci.org/Isilon/isilon_sdk)
[![](http://issuestats.com/github/isilon/isilon_sdk/badge/pr?style=flat-square)](http://issuestats.com/github/isilon/isilon_sdk)
[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/isilon/isilon_sdk.svg)](http://isitmaintained.com/project/isilon/isilon_sdk "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/isilon/isilon_sdk.svg)](http://isitmaintained.com/project/isilon/isilon_sdk "Percentage of issues still open")


# Isilon Software Development Kit (isi-sdk)
Language bindings for the OneFS API and tools for building them

This repository is part of the Isilon SDK.  It includes language bindings for easier programmatic access to the OneFS API for cluster configuration (on your cluster this is the REST API made up of all the URIs underneath `https://[cluster]:8080/platform/*`, also called the "Platform API" or "PAPI"). The SDK also includes language bindings for the OneFS RAN (i.e. RESTful Access to Namespace) interface, which provides access to the OneFS filesystem namespace.

You can download the language bindings for Python from the "releases" page of this repo (the link is on the main "code" tab on the bar of links just below the project description). If you just want to access PAPI more easily from your Python programs, these language bindings may be all you need, and you can follow the instructions and example below to get started.

This repository also includes tools to build PAPI bindings yourself for a large range of other programming languages. For more info see the [readme.dev.md](readme.dev.md) file in this directory.

### Installing the pre-built Python PAPI bindings

#### Prerequisites

* [Python](https://www.python.org/downloads/) 2.7 or later
* [pip](https://pip.pypa.io/en/stable/installing/)

#### Installing the package

`pip install isilon-sdk`

| Cluster Version Supported   | Module Name                 |
|-----------------------------|-----------------------------|
| OneFS 9.5.0.0               | `isilon_sdk.v9_5_0` |
| OneFS 9.4.0.0               | `isilon_sdk.v9_4_0` |
| OneFS 9.3.0.0               | `isilon_sdk.v9_3_0` |
| OneFS 9.2.1.0               | `isilon_sdk.v9_2_1` |
| OneFS 9.2.0.0               | `isilon_sdk.v9_2_0` |
| OneFS 9.1.0.0               | `isilon_sdk.v9_1_0` |
| OneFS 9.0.0.0               | `isilon_sdk.v9_0_0` |

Installation will default to using binary distribution wheel (i.e. bdist). Source distributions (i.e. sdist) are also available on pip beginning with v0.1.6 and can be installed with `pip install --no-binary :all: <pkg name>`

### Basic Usage

See the generated packages on PyPI for example code:

[isilon\_sdk](https://pypi.org/project/isilon-sdk)

### Bindings Documentation

The most up-to-date documentation for the language bindings is included in the root directory of your downloaded release package (or of your own generated bindings if you've generated your own using the instructions at [readme.dev.md](readme.dev.md)). It is a set of markdown files starting with the README.md in the root directory of the package. Otherwise, the documentation for the Python language bindings can be found in the [isilon_sdk_python](https://github.com/Isilon/isilon_sdk_python) repository where the branch names are associated with the OneFS release that the bindings were built against.

### Other Isilon SDK and API links:

* For OneFS API reference documents, discussions, and blog posts, refer to the [Isilon SDK Info Hub](https://community.emc.com/docs/DOC-48273).
* To browse the Isilon InsightIQ statistics API, refer to the [Stat Key Browser](https://github.com/isilon/isilon_stat_browser.git) Github repository.
