import swagger_client
import urllib3

urllib3.disable_warnings()
# configure username and password
swagger_client.configuration.username = "root"
swagger_client.configuration.password = "a"
swagger_client.configuration.verify_ssl = False

# configure host
host = "https://10.7.160.60:8080"
apiClient = swagger_client.ApiClient(host)
antivirusApi = swagger_client.AntivirusApi(apiClient)

# create scan item
newScanItem = swagger_client.AntivirusScanItem()
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
