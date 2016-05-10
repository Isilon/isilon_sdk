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

settings = antivirusApi.get_antivirus_settings()
print "Settings=" + str(settings)

settings.settings.repair = not settings.settings.repair
antivirusApi.update_antivirus_settings(settings.settings)

# verify it worked
updated = antivirusApi.get_antivirus_settings()

print "It worked: " + str(settings.settings.repair
                            == updated.settings.repair)

print "Done."
