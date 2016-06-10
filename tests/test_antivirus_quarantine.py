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

# update quarantine path
updateQuarantinePathParams = isi_sdk.AntivirusQuarantinePathParams()
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
