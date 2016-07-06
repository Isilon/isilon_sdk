[![Build Status](https://travis-ci.org/Isilon/isilon_sdk.svg?branch=master)](https://travis-ci.org/Isilon/isilon_sdk)
[![](http://issuestats.com/github/isilon/isilon_sdk/badge/pr?style=flat-square)](http://issuestats.com/github/isilon/isilon_sdk)
[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/isilon/isilon_sdk.svg)](http://isitmaintained.com/project/isilon/isilon_sdk "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/isilon/isilon_sdk.svg)](http://isitmaintained.com/project/isilon/isilon_sdk "Percentage of issues still open")


# Isilon Software Development Kit (isi-sdk)
Language bindings for the OneFS API and tools for building them

This repository is part of the Isilon SDK.  It includes language bindings for easier programmatic access to the OneFS API for cluster configuration (on your cluster this is the REST API made up of all the URIs underneath https://[cluster]:8080/platform/*, also called the "Platform API" or PAPI").

You can download the language bindings for Python from the "releases" page of this repo (the link is on the main "code" tab on the bar of links just below the project description).  If you just want to access PAPI more easily from your Python programs, these language bindings may be all you need, and you can follow the instructions and example below to get started.

This repository also includes tools to build PAPI bindings yourself for a large range of other programming languages.  For more info see the [readme.dev.md](readme.dev.md) file in this directory.

### Installing the pre-built Python PAPI bindings

#### Prerequisites

* [Python](https://www.python.org/downloads/) 2.7 or later
* [pip](https://pip.pypa.io/en/stable/installing/)

#### Installing the package

If you will only connect to OneFS 8.0 and later clusters:

`pip install isi_sdk_8_0`

If connecting to OneFS 7.2 and later clusters:

`pip install isi_sdk_7_2`

### Basic Usage

See the generated packages on PyPI for example code:

[isi\_sdk\_8\_0](https://pypi.python.org/pypi/isi-sdk-8-0)

[isi\_sdk\_7\_2](https://pypi.python.org/pypi/isi-sdk-7-2)

### Bindings Documentation

The most up-to-date documentation for the language bindings is included in the root directory of your downloaded release package (or of your own generated bindings if you've generated your own using the instructions at [readme.dev.md](readme.dev.md)).  It is a set of markdown files starting with the README.md in the root directory of the package.

We intend to also publish online docs as part of the build process for this repo's releases, but we haven't finished setting that up yet.  Meanwhile, if you really need online docs, some are still available at the legacy bindings repos linked below, but these will gradually be going out of sync with the latest bindings releases in this repo.

- [Legacy 8.0 Bindings Docs](https://github.com/Isilon/isilon_sdk_8_0_python)

- [Legacy 7.2 Bindings Docs](https://github.com/Isilon/isilon_sdk_7_2_python)

### Other Isilon SDK and API links:

* For OneFS API reference documents, discussions, and blog posts, refer to the [Isilon SDK Info Hub](https://community.emc.com/docs/DOC-48273).
* To browse the Isilon InsightIQ statistics API, refer to the [Stat Key Browser](https://github.com/isilon/isilon_stat_browser.git) Github repository.


