import isi_sdk as isi_sdk
from isi_sdk.rest import ApiException
import urllib3
import test_constants

from pprint import pprint

urllib3.disable_warnings()

# configure username and password
isi_sdk.configuration.username = test_constants.USERNAME
isi_sdk.configuration.password = test_constants.PASSWORD
isi_sdk.configuration.verify_ssl = test_constants.VERIFY_SSL

# configure host
host = test_constants.HOST
api_client = isi_sdk.ApiClient(host)
api_instance = isi_sdk.NetworkGroupnetsApi(api_client)

try:

    api_response = \
            api_instance.list_subnets_subnet_pools('groupnet0', 'subnet0')
    pprint(api_response)

except ApiException as e:

    print "Exception when calling list_subnets_subnet_pools: %s\n" % e
