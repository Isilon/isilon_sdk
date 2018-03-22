import urllib3

import isi_sdk_8_0 as isi_sdk

import test_constants

urllib3.disable_warnings()


# configure username and password
configuration = isi_sdk.Configuration()
configuration.username = test_constants.USERNAME
configuration.password = test_constants.PASSWORD
configuration.verify_ssl = test_constants.VERIFY_SSL
configuration.host = test_constants.HOST

# configure client connection
api_client = isi_sdk.ApiClient(configuration)
clusterApi = isi_sdk.ClusterApi(api_client)

timezone = clusterApi.get_cluster_timezone()

print("TimeZone: " + str(timezone))

print("Done.")
