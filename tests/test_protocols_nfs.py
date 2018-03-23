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

nfs_netgroup_settings = isi_sdk.NfsNetgroupSettings()
nfs_netgroup_settings.retry = 50
nfs_netgroup = isi_sdk.NfsNetgroup()
nfs_netgroup.settings = nfs_netgroup_settings

protocols_api.update_nfs_netgroup(nfs_netgroup)

test_nfs_netgroup = protocols_api.get_nfs_netgroup()

if test_nfs_netgroup.settings.retry != nfs_netgroup.settings.retry:
    raise RuntimeError("Netgroup Update Failed")

new_nfs_alias = isi_sdk.NfsAliasCreateParams(
    name="/FStress", path="/ifs/fstress")
try:
    protocols_api.create_nfs_alias(new_nfs_alias)
except isi_sdk.rest.ApiException as err:
    if err.status == 409:
        print("Alias already exists")
    else:
        raise err

nfs_aliases = protocols_api.list_nfs_aliases()
for nfs_alias in nfs_aliases.aliases:
    nfs_alias = protocols_api.get_nfs_alias(nfs_alias.id)
    print("NFS Alias: " + str(nfs_alias))

protocols_api.delete_nfs_alias(new_nfs_alias.name)
print("Deleted alias " + new_nfs_alias.name)
# get all exports
nfs_exports = protocols_api.list_nfs_exports()
print("NFS Exports:\n" + str(nfs_exports))

# get a specific export by id
get_export_resp = protocols_api.get_nfs_export(nfs_exports.exports[-1].id)

# update it with a PUT
an_export = get_export_resp.exports[0]
update_export = isi_sdk.NfsExport()

# toggle the symlinks parameter
update_export.symlinks = an_export.symlinks == False

protocols_api.update_nfs_export(nfs_export_id=an_export.id,
                                nfs_export=update_export)

# get it back and check that it worked
get_export_resp = protocols_api.get_nfs_export(an_export.id)

if get_export_resp.exports[0].symlinks != update_export.symlinks:
    raise RuntimeError("Update Failed.")


# create a new export
new_export = isi_sdk.NfsExport()
new_export.paths = ["/ifs/data"]

# use force because path already exists as export so would normally fail
create_resp = protocols_api.create_nfs_export(new_export, force=True)
print("Created=" + str(create_resp.id))
# now delete it
print("Deleting it.")
protocols_api.delete_nfs_export(nfs_export_id=create_resp.id)

# verify that it is deleted
# Note: my Error data model is not correct yet,
# so get on a non-existent nfs export id throws exception. Ideally it would
# just return an error response
try:
    print("Verifying delete.")
    resp = protocols_api.get_nfs_export(nfs_export_id=create_resp.id)
    print("Response should be 404, not: " + str(resp))
except isi_sdk.rest.ApiException:
    pass

print("Done.")
