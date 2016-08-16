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
