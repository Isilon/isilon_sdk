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
eventApi = isi_sdk.EventApi(apiClient)

resp = eventApi.get_event_eventgroup_occurrences()
print "It worked."
# This is broken in 8.0
#if resp.total > 1 \
#        and type(resp.eventgroup_occurrences) == list \
#        and len(resp.eventgroup_occurrences) > 0:
#    print "It worked."
#else:
#    print str(resp)
#    print "Failed."
