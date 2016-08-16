import isi_sdk
import urllib3
import test_constants

urllib3.disable_warnings()

# configure username and password
isi_sdk.configuration.username = test_constants.USERNAME
isi_sdk.configuration.password = test_constants.PASSWORD
isi_sdk.configuration.verify_ssl = test_constants.VERIFY_SSL

# configure host
host = test_constants.HOST
apiClient = isi_sdk.ApiClient(host)
clusterApi = isi_sdk.ClusterApi(apiClient)

# these two end points were throwing exceptions before so just testing that
# they have any response at all for now.
print str(clusterApi.get_cluster_config())
print "It worked."

print str(clusterApi.get_cluster_version())
print "Done."
