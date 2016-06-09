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

# create a new policy
newPolicy = isi_sdk.AntivirusPolicy()
newPolicy.paths = ["/ifs/data"]
newPolicy.name = "ifs_data"

# use force because path already exists as policy so would normally fail
createResp = antivirusApi.create_antivirus_policy(newPolicy)
print "Created=" + str(createResp.id)

# get it by id
getPolicyResp = antivirusApi.get_antivirus_policy(createResp.id)

# update it with a PUT
aPolicy = getPolicyResp.policies[0]

updatePolicy = isi_sdk.AntivirusPolicy()

# toggle the browsable parameter
updatePolicy.enabled = aPolicy.enabled == False

antivirusApi.update_antivirus_policy(antivirus_policy_id=aPolicy.id,
                                     antivirus_policy=updatePolicy)


# get it back and check that it worked
getPolicyResp = antivirusApi.get_antivirus_policy(aPolicy.id)

print "It worked == " \
        + str(getPolicyResp.policies[0].enabled == updatePolicy.enabled)

# get all policies
antivirusPolicies = antivirusApi.list_antivirus_policies()
print "Antivirus Policies:\n" + str(antivirusPolicies)

# now delete it
print "Deleting it."
antivirusApi.delete_antivirus_policy(antivirus_policy_id=createResp.id)

# verify that it is deleted
# Note: my Error data model is not correct yet,
# so get on a non-existent antivirus policy id throws exception. Ideally it would
# just return an error response
try:
    print "Verifying delete."
    resp = antivirusApi.get_antivirus_policy(antivirus_policy_id=createResp.id)
    print "Response should be 404, not: " + str(resp)
except isi_sdk.rest.ApiException:
    pass

print "Done."
