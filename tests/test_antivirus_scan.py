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
antivirusApi = isi_sdk.AntivirusApi(apiClient)

# create scan item
newScanItem = isi_sdk.AntivirusScanItem()
newScanItem.file = "/ifs/README.txt"

# You'll have to specify an antivirus icap server before this will work.
# POST the following body to /platform/3/antivirus/servers to enable it.
# {
#     "url": "icap://YOUR_ICAP_SERVER_ADDRESS",
#     "enabled": True
# }

scanResult = \
        antivirusApi.create_antivirus_scan_item(
                antivirus_scan_item=newScanItem)

print "Scan result == " + str(scanResult)

print "Done."
