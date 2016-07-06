## About
This package is part of the Isilon SDK.  It includes language bindings for easier programmatic access to the OneFS API for cluster configuration (on your cluster this is the REST API made up of all the URIs underneath https://[cluster]:8080/platform/*, also called the "Platform API" or PAPI").

## Installation

`pip install PKG_NAME`


## Example program

Here's an example of using the Python PAPI bindings to retrieve a list of NFS exports from your cluster:

```python
import PKG_NAME
from PKG_NAME.rest import ApiException
from pprint import pprint
import urllib3
urllib3.disable_warnings()

# configure username and password
PKG_NAME.configuration.username = "YOUR_USERNAME"
PKG_NAME.configuration.password = "YOUR_PASSWORD"
PKG_NAME.configuration.verify_ssl = False

# configure host
host = "https://YOUR_CLUSTER_HOSTNAME_OR_NODE_IP_ADDRESS:8080"
api_client = PKG_NAME.ApiClient(host)
protocols_api = PKG_NAME.ProtocolsApi(api_client)

# get all exports
sort = "description"
limit = 50
dir = "ASC"
try: 
    api_response = protocols_api.list_nfs_exports(sort=sort, limit=limit, dir=dir)
    pprint(api_response)
except ApiException as e:
    print "Exception when calling ProtocolsApi->list_nfs_exports: %s" % e
```

There are more examples of coding to the Python PAPI bindings in the [`tests/`](https://github.com/Isilon/isilon_sdk/tree/master/tests) subdirectory of the repo.  The tests currently run against a generic isi_sdk import which is how the bindings library is named by default if you build your own bindings.  If you want to run the tests against one of the libraries you've downloaded from the prebuilt releases page, you should change the `import isi_sdk` lines to `import isi_sdk_7_2` or `import isi_sdk_8_0` depending on which one you downloaded.

## More info
See the Github repo for more information:
[https://github.com/isilon/isilon_sdk](https://github.com/isilon/isilon_sdk)
