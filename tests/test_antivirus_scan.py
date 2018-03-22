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

# create scan item
new_scan_item = isi_sdk.AntivirusScanItem(file="/ifs/README.txt")

# You'll have to specify an antivirus icap server before this will work.
# POST the following body to /platform/3/antivirus/servers to enable it.
# {
#     "url": "icap://YOUR_ICAP_SERVER_ADDRESS",
#     "enabled": True
# }

scan_result = \
    antivirus_api.create_antivirus_scan_item(
        antivirus_scan_item=new_scan_item)

print("Scan result == " + str(scan_result))
print("Done.")
