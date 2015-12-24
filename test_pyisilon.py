import swagger_client

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
# the data model returned by the get_nfs_export is not compatible with the data
# model required by a PUT and/or POST (there extra information in the response
# from the "GET" queries, which when the same object/data model is used in a
# PUT or POST the PAPI gives an error. So we have to define/create new objects.
# NOTE: There's actually an ApiClient::__deserialize_model function that can
# build an object from a dict, which would allow the different data models to
# translate between each other, e.g.:
# updateExport =
#     apiClient.__deserializeModel(anExport.to_dict(),swagger_client.NfsExport)
# its too bad that the data models don't directly support construction from a
# dict (seems easy enough considering they support "to_dict", might as well
# support "from_dict", perhaps can request a new Swagger feature. Although,
# ideally the Isilon PAPI data models were consistent or at least weren't so
# strict about extra data.
updateExport = swagger_client.NfsExport()

# toggle the symlinks parameter
updateExport.symlinks = anExport.symlinks == False

protocolsApi.update_nfs_export(nfs_export_id=anExport.id,
                               nfs_export=updateExport)

# get it back and check that it worked
getExportResp = protocolsApi.get_nfs_export(anExport.id)

print "It worked == " \
        + str(getExportResp.exports[0].symlinks == updateExport.symlinks)


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
protocolsApi.get_nfs_export(nfs_export_id=createResp.id)
