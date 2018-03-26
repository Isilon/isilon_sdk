import urllib3

import isi_sdk_8_0 as isi_sdk
from isi_sdk_8_0.rest import ApiException

import test_constants

urllib3.disable_warnings()


def main():
    # configure username and password
    configuration = isi_sdk.Configuration()
    configuration.username = test_constants.USERNAME
    configuration.password = test_constants.PASSWORD
    configuration.verify_ssl = test_constants.VERIFY_SSL
    configuration.host = test_constants.HOST

    # configure client connection
    api_client = isi_sdk.ApiClient(configuration)
    api_instance = isi_sdk.NetworkGroupnetsApi(api_client)

    try:
        api_response = \
            api_instance.list_subnets_subnet_pools('groupnet0', 'subnet0')
        print(api_response)

    except ApiException as e:
        print("Exception when calling list_subnets_subnet_pools: %s\n" % e)


if __name__ == '__main__':
    main()
