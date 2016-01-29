import swagger_client
import urllib3

urllib3.disable_warnings()
# configure username and password
swagger_client.configuration.username = "root"
swagger_client.configuration.password = "a"
swagger_client.configuration.verify_ssl = False

# configure host
host = "https://137.69.154.252:8080"
apiClient = swagger_client.ApiClient(host)
antivirusApi = swagger_client.AntivirusApi(apiClient)

# create scan item
newScanItem = swagger_client.AntivirusScanItem()
newScanItem.file = "/ifs/README.txt"

scanResult = \
        antivirusApi.create_antivirus_scan_item(
                antivirus_scan_item=newScanItem)

print "Scan result == " + str(scanResult)

print "Done."
