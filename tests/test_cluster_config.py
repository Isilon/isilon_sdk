import urllib3

import isi_sdk_8_1_0 as isi_sdk

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
    cluster_api = isi_sdk.ClusterApi(api_client)

    # these two end points were throwing exceptions before so just testing that
    # they have any response at all for now.
    print(str(cluster_api.get_cluster_config()))
    print("It worked.")

    print(str(cluster_api.get_cluster_version()))
    print("It worked.")

    print(str(cluster_api.get_cluster_external_ips()))
    print("Done.")


if __name__ == '__main__':
    main()
