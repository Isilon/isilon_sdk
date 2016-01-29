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

# create a new policy
newPolicy = swagger_client.AntivirusPolicy()
newPolicy.paths = ["/ifs/data"]
newPolicy.name = "ifs_data"

# use force because path already exists as policy so would normally fail
createResp = antivirusApi.create_antivirus_policy(newPolicy)
print "Created=" + str(createResp.id)

# get it by id
getPolicyResp = antivirusApi.get_antivirus_policy(createResp.id)

# update it with a PUT
aPolicy = getPolicyResp.policies[0]

updatePolicy = swagger_client.AntivirusPolicy()

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
except swagger_client.rest.ApiException:
    pass

print "Done."
