About
-----

This package is part of the Isilon SDK. It includes language bindings
for easier programmatic access to the OneFS API for cluster
configuration (on your cluster this is the REST API made up of all the
URIs underneath ``https://[cluster]:8080/platform/*``, also called the
"Platform API" or "PAPI"). The SDK also includes language bindings for
the OneFS RAN (i.e. RESTful Access to Namespace) interface, which
provides access to the OneFS filesystem namespace.

Installation
------------

``pip install isilon_sdk``

Example program
---------------

Please select the subpackage as applicable to the OneFS version of your
cluster by referring to the below table:


OneFS Version and respective package names are as:

============= ==================
OneFS Release Package Name      
9.5.0.0       isilon_sdk.v9_5_0 
9.6.0.0       isilon_sdk.v9_6_0 
9.7.0.0       isilon_sdk.v9_7_0 
9.8.0.0       isilon_sdk.v9_8_0 
9.9.0.0       isilon_sdk.v9_9_0 
9.10.0.0      isilon_sdk.v9_10_0
9.11.0.0      isilon_sdk.v9_11_0
9.12.0.0      isilon_sdk.v9_12_0
============= ==================

Here’s an example of using the Python PAPI bindings to retrieve a list
of NFS exports from your clusters

::

   from __future__ import print_function

   from pprint import pprint
   import time
   import urllib3

   import isilon_sdk.v9_12_0
   from isilon_sdk.v9_12_0.rest import ApiException

   urllib3.disable_warnings()

   # configure cluster connection: basicAuth
   configuration = isilon_sdk.v9_12_0.Configuration()
   configuration.host = 'https://<NODE_IP>:8080'
   configuration.username = 'root'
   configuration.password = 'a'
   configuration.verify_ssl = False

   # create an instance of the API class
   api_client = isilon_sdk.v9_12_0.ApiClient(configuration)
   api_instance = isilon_sdk.v9_12_0.ProtocolsApi(api_client)

   # get all exports
   sort = 'description'
   limit = 50
   order = 'ASC'
   try:
       api_response = api_instance.list_nfs_exports(sort=sort, limit=limit, dir=order)
       pprint(api_response)
   except ApiException as e:
       print("Exception when calling ProtocolsApi->list_nfs_exports: %s\n" % e)

More Info
---------------
See the Github repo for more information:
https://github.com/isilon/isilon_sdk