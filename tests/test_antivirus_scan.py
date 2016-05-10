import isi_sdk
import urllib3

urllib3.disable_warnings()
# configure username and password
isi_sdk.configuration.username = "root"
isi_sdk.configuration.password = "a"
isi_sdk.configuration.verify_ssl = False

# configure host
host = "https://VNODE2294.west.isilon.com:8080"
apiClient = isi_sdk.ApiClient(host)
antivirusApi = isi_sdk.AntivirusApi(apiClient)

# create scan item
newScanItem = isi_sdk.AntivirusScanItem()
newScanItem.file = "/ifs/README.txt"

# You'll have to specify an antivirus icap server before this will work.
# Our isilon icap server is at 10.111.219.215.  POST the following body to
# /platform/3/antivirus/servers to enable it.
# {
#     "url": "icap://10.111.219.215",
#     "enabled": True
# }

scanResult = \
        antivirusApi.create_antivirus_scan_item(
                antivirus_scan_item=newScanItem)

print "Scan result == " + str(scanResult)

print "Done."
