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
