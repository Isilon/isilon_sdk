# Isilon Software Development Kit (isi-sdk)
Language bindings for the OneFS API and tools for building them

This repository is part of the Isilon SDK.  It includes language bindings for easier programmatic access to the OneFS API for cluster configuration (on your cluster this is the REST API made up of all the URIs underneath https://[cluster]:8080/platform/*, also called the "Platform API" or PAPI").

You can download the language bindings for Python from the "releases" page of this repo (the link is on the main "code" tab on the bar of links just below the project description).  If you just want to access PAPI more easily from your Python programs, these language bindings may be all you need, and you can follow the instructions and example below to get started.

This repository also includes tools to build PAPI bindings yourself for a large range of other programming languages.  For more info see the [readme.dev.md](readme.dev.md) file in this directory.

### Installing the pre-built Python PAPI bindings

1. Download the latest package from the "releases" page of this repo.

2. Install via [Setuptools](http://pypi.python.org/pypi/setuptools).  For example, unzip the package archive to a directory and from there run:

```sh
python setup.py install --user
```
(or `sudo python setup.py install` to install the package for all users)

You may need to install the Python [Setuptools](http://pypi.python.org/pypi/setuptools) on your system, if they are not already installed. For instructions, see http://pypi.python.org/pypi/setuptools.

Then at a Python prompt or in your Python programs, import the package:
```python
import isi_sdk_8_0 # or isi_sdk_7_2, depending on the release you downloaded
```

## Example program

Here's an example of using the Python PAPI bindings to retrieve a list of NFS exports from your cluster:

```python
import isi_sdk_8_0 # or isi_sdk_7_2, depending on the release you downloaded
from isi_sdk_8_0.rest import ApiException
from pprint import pprint
import urllib3
urllib3.disable_warnings()

# configure username and password
isi_sdk_8_0.configuration.username = "YOUR_USERNAME"
isi_sdk_8_0.configuration.password = "YOUR_PASSWORD"
isi_sdk_8_0.configuration.verify_ssl = False

# configure host
host = "https://YOUR_CLUSTER_HOSTNAME_OR_NODE_IP_ADDRESS:8080"
api_client = isi_sdk_8_0.ApiClient(host)
protocols_api = isi_sdk_8_0.ProtocolsApi(api_client)

# get all exports
sort = "description"
limit = 50
dir = "ASC"
try: 
    api_response = protocols_api.list_nfs_exports(sort=sort, limit=limit, dir=dir)
    pprint(api_response)
except ApiException as e:
    print "Exception when calling ProtocolsApi->list_nfs_exports: %s\n" % e
```

There are more examples of coding to the Python PAPI bindings in the `tests/` subdirectory of this repo.  The tests currently run against a generic isi_sdk import which is how the bindings library is named by default if you build your own bindings.  If you want to run the tests against one of the libraries you've downloaded from the prebuilt releases page, you should change the `import isi_sdk` lines to `import isi_sdk_7_2` or `import isi_sdk_8_0` depending on which one you downloaded.

### Bindings Documentation

The most up-to-date documentation for the language bindings is included in the root directory of your downloaded release package (or of your own generated bindings if you've generated your own using the instructions at [readme.dev.md](readme.dev.md)).  It is a set of markdown files starting with the README.md in the root directory of the package.

We intend to also publish online docs as part of the build process for this repo's releases, but we haven't finished setting that up yet.  Meanwhile, if you really need online docs, some are still available at the legacy bindings repos linked below, but these will gradually be going out of sync with the latest bindings releases in this repo.

- [Legacy 8.0 Bindings Docs](https://github.com/Isilon/isilon_sdk_8_0_python)

- [Legacy 7.2 Bindings Docs](https://github.com/Isilon/isilon_sdk_7_2_python)

### Other Isilon SDK and API links:

* For OneFS API reference documents, discussions, and blog posts, refer to the [Isilon SDK Info Hub](https://community.emc.com/docs/DOC-48273).
* To browse the Isilon InsiqhtIQ statistics API, refer to the [Stat Key Browser](https://github.com/isilon/isilon_stat_browser.git) Github repository.


