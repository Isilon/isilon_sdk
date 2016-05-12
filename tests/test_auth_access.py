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
authApi = isi_sdk.AuthApi(apiClient)

accessUser = "root"
path = "/ifs/data"

getAccessUserResp = \
        authApi.get_auth_access_user(auth_access_user=accessUser, path=path)

print "It worked: " + str(getAccessUserResp.access[0].id == accessUser)

print "Done."
