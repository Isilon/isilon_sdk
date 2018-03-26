import urllib3

import isi_sdk_8_0 as isi_sdk

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
    auth_api = isi_sdk.AuthApi(api_client)

    accessUser = "root"
    path = "/ifs/data"

    get_access_user_resp = auth_api.get_auth_access_user(
        auth_access_user=accessUser, path=path)

    print("It worked: " + str(get_access_user_resp.access[0].id == accessUser))

    print("Done.")


if __name__ == '__main__':
    main()
