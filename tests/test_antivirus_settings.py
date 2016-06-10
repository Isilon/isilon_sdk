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

settings = antivirusApi.get_antivirus_settings()
print "Settings=" + str(settings)

settings.settings.repair = not settings.settings.repair
antivirusApi.update_antivirus_settings(settings.settings)

# verify it worked
updated = antivirusApi.get_antivirus_settings()

print "It worked: " + str(settings.settings.repair
                            == updated.settings.repair)

print "Done."
