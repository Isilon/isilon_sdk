import swagger_client

# configure username and password
swagger_client.configuration.username = "root"
swagger_client.configuration.password = "a"
swagger_client.configuration.verify_ssl = False

# configure host
host = "https://137.69.154.252:8080"
apiClient = swagger_client.ApiClient(host)
protocolsApi = swagger_client.ProtocolsApi(apiClient)

nfsExports = protocolsApi.list_nfs_exports()
print "NFS Exports:\n" + str(nfsExports)

# get a specific export by id
getExportResp = protocolsApi.get_nfs_export_by_id(nfsExports.exports[-1].id)

# update it with a PUT
anExport = getExportResp.exports[0]
anExportId = anExport.id
# unset these because they mess up the PUT
anExport.id = None
anExport.snapshot = None
anExport.map_all = None
anExport.conflicting_paths = None
anExport.unresolved_clients = None

anExport.symlinks = anExport.symlinks == False

protocolsApi.update_nfs_export(nfs_export_id=anExportId, nfs_export=anExport)

newExport = swagger_client.NfsExport()
newExport.paths = ["/ifs/data"]

createResp = protocolsApi.create_nfs_export(newExport, force=True)
print "Created=" + str(createResp.id)
# now delete it
print "Deleting it."
protocolsApi.delete_nfs_export(nfs_export_id=createResp.id)
