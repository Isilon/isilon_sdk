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
    quota_api = isi_sdk.QuotaApi(api_client)

    new_quota = isi_sdk.QuotaQuotaCreateParams(
        enforced=False,
        include_snapshots=False,
        thresholds_include_overhead=False,
        path="/ifs/data",
        type="directory")

    create_resp = quota_api.create_quota_quota(quota_quota=new_quota)
    print("Created=" + str(create_resp))

    print(str(quota_api.list_quota_quotas()))

    delete_resp = quota_api.delete_quota_quotas(path=new_quota.path)
    print("Delete response=" + str(delete_resp))

    print("It worked.")


if __name__ == '__main__':
    main()
