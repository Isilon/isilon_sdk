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
antivirus_api = isi_sdk.AntivirusApi(api_client)

# update quarantine path
update_quarantine_path_params = isi_sdk.AntivirusQuarantinePathParams()
update_quarantine_path_params.quarantined = True

quarantine_path = "ifs/README.txt"
antivirus_api.update_antivirus_quarantine_path(
    antivirus_quarantine_path=quarantine_path,
    antivirus_quarantine_path_params=update_quarantine_path_params)

# get it back and check that it worked
get_quarantine_path_resp = \
    antivirus_api.get_antivirus_quarantine_path(quarantine_path)
print("It worked == " +
      str(get_quarantine_path_resp.quarantined ==
          update_quarantine_path_params.quarantined))

# now unquarantine it
update_quarantine_path_params.quarantined = False
antivirus_api.update_antivirus_quarantine_path(
    antivirus_quarantine_path=quarantine_path,
    antivirus_quarantine_path_params=update_quarantine_path_params)

# verify it is no longer quarantined
get_quarantine_path_resp = \
    antivirus_api.get_antivirus_quarantine_path(quarantine_path)
print("It worked == " +
      str(get_quarantine_path_resp.quarantined ==
          update_quarantine_path_params.quarantined))

print("Done.")
