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
authApi = isi_sdk.AuthApi(apiClient)

accessUser = "root"
path = "/ifs/data"

getAccessUserResp = \
        authApi.get_auth_access_user(auth_access_user=accessUser, path=path)

print "It worked: " + str(getAccessUserResp.access[0].id == accessUser)

print "Done."
