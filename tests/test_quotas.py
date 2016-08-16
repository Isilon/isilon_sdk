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
quotaApi = isi_sdk.QuotaApi(apiClient)

newQuota = isi_sdk.QuotaQuotaCreateParams()
newQuota.enforced = False
newQuota.include_snapshots = False
newQuota.thresholds_include_overhead = False
newQuota.path = "/ifs/data"
newQuota.type = "directory"

createResp = quotaApi.create_quota_quota(quota_quota=newQuota)
print "Created=" + str(createResp)

print str(quotaApi.list_quota_quotas())

deleteResp = quotaApi.delete_quota_quotas(path=newQuota.path)
print str(deleteResp)

print "It worked."
