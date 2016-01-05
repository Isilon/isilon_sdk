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

# update quarantine item
updateQuarantineItem = swagger_client.AntivirusQuarantineItem()
updateQuarantineItem.quarantined = True

quarantineItemId = "/ifs/README.txt"
antivirusApi.update_antivirus_quarantine_item(
        antivirus_quarantine_item_id=quarantineItemId,
        antivirus_quarantine_item=updateQuarantineItem)


# get it back and check that it worked
getQuarantineItemResp = \
        antivirusApi.get_antivirus_quarantine_item(quarantineItemId)
print "It worked == " \
        + str(getQuarantineItemResp.quarantined
                == updateQuarantineItem.quarantined)

# now unquarantine it
updateQuarantineItem.quarantined = False
antivirusApi.update_antivirus_quarantine_item(
        antivirus_quarantine_item_id=quarantineItemId,
        antivirus_quarantine_item=updateQuarantineItem)

# verify it is no longer quarantined
getQuarantineItemResp = \
        antivirusApi.get_antivirus_quarantine_item(quarantineItemId)
print "It worked == " \
        + str(getQuarantineItemResp.quarantined
                == updateQuarantineItem.quarantined)

print "Done."
