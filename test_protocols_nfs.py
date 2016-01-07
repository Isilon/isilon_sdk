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
protocolsApi = swagger_client.ProtocolsApi(apiClient)

# get all exports
nfsExports = protocolsApi.list_nfs_exports()
print "NFS Exports:\n" + str(nfsExports)

# get a specific export by id
getExportResp = protocolsApi.get_nfs_export(nfsExports.exports[-1].id)

# update it with a PUT
anExport = getExportResp.exports[0]
updateExport = swagger_client.NfsExport()

# toggle the symlinks parameter
updateExport.symlinks = anExport.symlinks == False

protocolsApi.update_nfs_export(nfs_export_id=anExport.id,
                               nfs_export=updateExport)

# get it back and check that it worked
getExportResp = protocolsApi.get_nfs_export(anExport.id)

if getExportResp.exports[0].symlinks != updateExport.symlinks:
    raise RuntimeError("Update Failed.")


# create a new export
newExport = swagger_client.NfsExport()
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
except swagger_client.rest.ApiException:
    pass

print "Done."
