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

settings = antivirusApi.get_antivirus_settings()
print "Settings=" + str(settings)

settings.settings.repair = False
antivirusApi.update_antivirus_settings(settings.settings)

# verify it worked
updated = antivirusApi.get_antivirus_settings()

print "It worked: " + str(settings.settings.repair
                            == updated.settings.repair)

print "Done."
