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
authApi = swagger_client.AuthApi(apiClient)

accessUser = "root"
path = "/ifs/data"

getAccessUserResp = \
        authApi.get_auth_access_user(auth_access_user=accessUser, path=path)

print "It worked: " + str(getAccessUserResp.access[0].id == accessUser)

print "Done."
