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
protocolsApi = isi_sdk.ProtocolsApi(apiClient)

# get all shares
smbShares = protocolsApi.list_smb_shares()
print "SMB Shares:\n" + str(smbShares)

# get a specific share by id
getShareResp = protocolsApi.get_smb_share(smbShares.shares[-1].id)

# update it with a PUT
aShare = getShareResp.shares[0]
# the data model returned by the get_smb_share is not compatible with the data
# model required by a PUT and/or POST (there extra information in the response
# from the "GET" queries, which when the same object/data model is used in a
# PUT or POST the PAPI gives an error. So we have to define/create new objects.
# NOTE: There's actually an ApiClient::__deserialize_model function that can
# build an object from a dict, which would allow the different data models to
# translate between each other, e.g.:
# updateShare =
#     apiClient.__deserializeModel(aShare.to_dict(),isi_sdk.SmbShare)
# its too bad that the data models don't directly support construction from a
# dict (seems easy enough considering they support "to_dict", might as well
# support "from_dict", perhaps can request a new Swagger feature. Although,
# ideally the Isilon PAPI data models were consistent or at least weren't so
# strict about extra data.
updateShare = isi_sdk.SmbShare()

# toggle the browsable parameter
updateShare.browsable = aShare.browsable == False

protocolsApi.update_smb_share(smb_share_id=aShare.id,
                              smb_share=updateShare)

# get it back and check that it worked
getShareResp = protocolsApi.get_smb_share(aShare.id)

print "It worked == " \
        + str(getShareResp.shares[0].browsable == updateShare.browsable)

# create a new share
newShare = isi_sdk.SmbShareCreateParams()
newShare.path = "/ifs/data"
newShare.name = "ifs_data"

# use force because path already exists as share so would normally fail
createResp = protocolsApi.create_smb_share(newShare)
print "Created=" + str(createResp.id)
# now delete it
print "Deleting it."
protocolsApi.delete_smb_share(smb_share_id=createResp.id)

# verify that it is deleted
# Note: my Error data model is not correct yet,
# so get on a non-existent smb share id throws exception. Ideally it would
# just return an error response
try:
    print "Verifying delete."
    resp = protocolsApi.get_smb_share(smb_share_id=createResp.id)
    print "Response should be 404, not: " + str(resp)
except isi_sdk.rest.ApiException:
    pass

print "Done."
