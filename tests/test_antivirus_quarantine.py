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

# update quarantine path
updateQuarantinePathParams = swagger_client.AntivirusQuarantinePathParams()
updateQuarantinePathParams.quarantined = True

quarantinePath = "/ifs/README.txt"
antivirusApi.update_antivirus_quarantine_path(
        antivirus_quarantine_path=quarantinePath,
        antivirus_quarantine_path_params=updateQuarantinePathParams)


# get it back and check that it worked
getQuarantinePathResp = \
        antivirusApi.get_antivirus_quarantine_path(quarantinePath)
print "It worked == " \
        + str(getQuarantinePathResp.quarantined
                == updateQuarantinePathParams.quarantined)

# now unquarantine it
updateQuarantinePathParams.quarantined = False
antivirusApi.update_antivirus_quarantine_path(
        antivirus_quarantine_path=quarantinePath,
        antivirus_quarantine_path_params=updateQuarantinePathParams)

# verify it is no longer quarantined
getQuarantinePathResp = \
        antivirusApi.get_antivirus_quarantine_path(quarantinePath)
print "It worked == " \
        + str(getQuarantinePathResp.quarantined
                == updateQuarantinePathParams.quarantined)

print "Done."
