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

nfs_netgroup_settings = isi_sdk.NfsNetgroupSettings()
nfs_netgroup_settings.retry = 50
nfs_netgroup = isi_sdk.NfsNetgroup()
nfs_netgroup.settings = nfs_netgroup_settings

protocolsApi.update_nfs_netgroup(nfs_netgroup)

test_nfs_netgroup = protocolsApi.get_nfs_netgroup()

if test_nfs_netgroup.settings.retry != nfs_netgroup.settings.retry:
    raise RuntimeError("Netgroup Update Failed")

new_nfs_alias = isi_sdk.NfsAliaseCreateParams()
new_nfs_alias.name = "/FStress"
new_nfs_alias.path = "/ifs/fstress"
protocolsApi.create_nfs_aliase(new_nfs_alias)

nfs_aliases = protocolsApi.list_nfs_aliases()
for nfs_alias in nfs_aliases.aliases:
    nfs_alias = protocolsApi.get_nfs_aliase(nfs_alias.id)
    print "NFS Alias: " + str(nfs_alias)

protocolsApi.delete_nfs_aliase(new_nfs_alias.name)
print "Deleted alias " + new_nfs_alias.name
# get all exports
nfsExports = protocolsApi.list_nfs_exports()
print "NFS Exports:\n" + str(nfsExports)

# get a specific export by id
getExportResp = protocolsApi.get_nfs_export(nfsExports.exports[-1].id)

# update it with a PUT
anExport = getExportResp.exports[0]
updateExport = isi_sdk.NfsExport()

# toggle the symlinks parameter
updateExport.symlinks = anExport.symlinks == False

protocolsApi.update_nfs_export(nfs_export_id=anExport.id,
                               nfs_export=updateExport)

# get it back and check that it worked
getExportResp = protocolsApi.get_nfs_export(anExport.id)

if getExportResp.exports[0].symlinks != updateExport.symlinks:
    raise RuntimeError("Update Failed.")


# create a new export
newExport = isi_sdk.NfsExport()
newExport.paths = ["/ifs/data"]

# use force because path already exists as export so would normally fail
createResp = protocolsApi.create_nfs_export(newExport, force=True)
print "Created=" + str(createResp.id)
# now delete it
print "Deleting it."
protocolsApi.delete_nfs_export(nfs_export_id=createResp.id)

# verify that it is deleted
# Note: my Error data model is not correct yet,
# so get on a non-existent nfs export id throws exception. Ideally it would
# just return an error response
try:
    print "Verifying delete."
    resp = protocolsApi.get_nfs_export(nfs_export_id=createResp.id)
    print "Response should be 404, not: " + str(resp)
except isi_sdk.rest.ApiException:
    pass

print "Done."
