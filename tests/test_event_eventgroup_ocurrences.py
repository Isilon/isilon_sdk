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
eventApi = isi_sdk.EventApi(api_client)

resp = eventApi.get_event_eventgroup_occurrences()

# This is broken in 8.0
if resp.total > 1 and resp.eventgroups and isinstance(resp.eventgroups, list):
    print("Received back %d eventgroups." % len(resp.eventgroups))
else:
    print(str(resp))
    print("Failed.")
