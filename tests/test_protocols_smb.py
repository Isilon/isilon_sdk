import json
import urllib3

import isi_sdk_8_1_0 as isi_sdk

import test_constants

urllib3.disable_warnings()


# configure username and password
configuration = isi_sdk.Configuration()
configuration.username = test_constants.USERNAME
configuration.password = test_constants.PASSWORD
configuration.verify_ssl = test_constants.VERIFY_SSL
configuration.host = test_constants.HOST

# configure client connection
api_client = isi_sdk.ApiClient(configuration)
protocols_api = isi_sdk.ProtocolsApi(api_client)

# get all shares
smb_shares = protocols_api.list_smb_shares()
print("SMB Shares:\n" + str(smb_shares))

# get a specific share by id
get_share_resp = protocols_api.get_smb_share(smb_shares.shares[-1].id)

# update it with a PUT
a_share = get_share_resp.shares[0]
# the data model returned by the get_smb_share is not compatible with the data
# model required by a PUT and/or POST (there extra information in the response
# from the "GET" queries, which when the same object/data model is used in a
# PUT or POST the PAPI gives an error. So we have to define/create new objects.
# NOTE: There's actually an ApiClient::__deserialize_model function that can
# build an object from a dict, which would allow the different data models to
# translate between each other, e.g.:
# update_share =
#     api_client.__deserializeModel(a_share.to_dict(), isi_sdk.SmbShare)
# its too bad that the data models don't directly support construction from a
# dict (seems easy enough considering they support "to_dict", might as well
# support "from_dict", perhaps can request a new Swagger feature. Although,
# ideally the Isilon PAPI data models were consistent or at least weren't so
# strict about extra data.
update_share = isi_sdk.SmbShare()

# toggle the browsable parameter
update_share.browsable = not a_share.browsable

protocols_api.update_smb_share(smb_share_id=a_share.id,
                               smb_share=update_share)

# get it back and check that it worked
get_share_resp = protocols_api.get_smb_share(a_share.id)

print("It worked == " +
      str(get_share_resp.shares[0].browsable == update_share.browsable))

# create a new share
new_share = isi_sdk.SmbShareCreateParams(name="ifs_data", path="/ifs/data")

try:
    create_resp = protocols_api.create_smb_share(new_share)
except isi_sdk.rest.ApiException as err:
    if err.status == 409:
        print(json.loads(err.body)['errors'][0]['message'])
        # share already exists, so look it up
        for share in protocols_api.list_smb_shares().shares:
            if share.name == new_share.name:
                share_id = share.id
    else:
        raise err
else:
    share_id = create_resp.id
    print("Created=" + str(share_id))

# now delete it
print("Deleting it.")
protocols_api.delete_smb_share(smb_share_id=share_id)

# verify that it is deleted
# Note: my Error data model is not correct yet,
# so get on a non-existent smb share id throws exception. Ideally it would
# just return an error response
try:
    print("Verifying delete.")
    resp = protocols_api.get_smb_share(smb_share_id=share_id)
    print("Response should be 404, not: " + str(resp))
except isi_sdk.rest.ApiException:
    pass

print("Done.")
