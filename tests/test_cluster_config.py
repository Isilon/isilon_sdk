import isi_sdk
import urllib3

urllib3.disable_warnings()

# configure username and password
isi_sdk.configuration.username = "root"
isi_sdk.configuration.password = "a"
isi_sdk.configuration.verify_ssl = False

# configure host
host = "https://VNODE2294.west.isilon.com:8080"
apiClient = isi_sdk.ApiClient(host)
clusterApi = isi_sdk.ClusterApi(apiClient)

# these two end points were throwing exceptions before so just testing that
# they have any response at all for now.
print str(clusterApi.get_cluster_config())
print "It worked."

print str(clusterApi.get_cluster_version())
print "Done."
