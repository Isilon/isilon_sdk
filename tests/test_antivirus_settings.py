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
    antivirus_api = isi_sdk.AntivirusApi(api_client)

    settings = antivirus_api.get_antivirus_settings()
    print("Settings=" + str(settings))

    settings.settings.repair = not settings.settings.repair
    antivirus_api.update_antivirus_settings(settings.settings)

    # verify it worked
    updated = antivirus_api.get_antivirus_settings()

    print("It worked: " +
          str(settings.settings.repair == updated.settings.repair))

    print("Done.")


if __name__ == '__main__':
    main()
