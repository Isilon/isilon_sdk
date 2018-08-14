"""Directories with isi_sdk.NamespaceApi."""
import urllib3

import isi_sdk_8_1_1 as isi_sdk

import test_constants

urllib3.disable_warnings()


def main():
    # configure username and password
    configuration = isi_sdk.Configuration()
    configuration.username = test_constants.USERNAME
    configuration.password = test_constants.PASSWORD
    configuration.verify_ssl = test_constants.VERIFY_SSL
    configuration.host = test_constants.HOST

    # configure client connection
    api_client = isi_sdk.ApiClient(configuration)
    api = isi_sdk.NamespaceApi(api_client)

    # create a directory
    api.create_directory(
        'ifs/ns_src/ns_dir', x_isi_ifs_target_type='container',
        recursive=True, overwrite=True)

    # recursively copy directory from /ifs/ns_src to /ifs/ns_dest
    api.copy_directory(
        'ifs/ns_dest', x_isi_ifs_copy_source='/namespace/ifs/ns_src',
        merge=True)
    print('Copied directory: {}'.format(
        api.get_directory_contents('ifs/ns_dest').children[0].name))
    api.delete_directory('ifs/ns_dest', recursive=True)

    # move directory from /ifs/ns_src to /ifs/ns_dest
    api.move_directory(
        'ifs/ns_src', x_isi_ifs_set_location='/namespace/ifs/ns_dest')
    print('Moved directory: {}'.format(
        api.get_directory_contents('ifs/ns_dest').children[0].name))
    api.delete_directory('ifs/ns_dest', recursive=True)

    # get directory attributes from response headers
    sdk_resp = api.get_directory_attributes_with_http_info('ifs/data')
    # the third index of the response is the response headers
    print('Directory attributes from headers: {}'.format(sdk_resp[2]))

    # get default directory detail
    details = api.get_directory_contents(
        'ifs', detail='default').children[0].to_dict()
    details = dict((k, v) for k, v in details.items() if v)
    print('Default directory details: {}'.format(details))
    # get directory last modified time
    print('Last modified time: {}'.format(
        api.get_directory_contents(
            'ifs', detail='last_modified').children[0].last_modified))

    # use resume token to paginate requests
    resume = api.get_directory_contents('ifs', limit=3).resume
    api.get_directory_contents('ifs', resume=resume)

    # get extended attributes on a directory
    print('Directory metadata attributes: {}'.format(
        api.get_directory_metadata('ifs', metadata=True)))
    # create extended attribute
    meta = isi_sdk.NamespaceMetadata(
        action='update',
        attrs=[isi_sdk.NamespaceMetadataAttrs(
            name='test', value='42', op='update', namespace='user')])
    # set extended attribute on a directory
    api.set_directory_metadata('ifs', metadata=True, directory_metadata=meta)
    # remove extended attribute
    meta = isi_sdk.NamespaceMetadata(
        action='update',
        attrs=[isi_sdk.NamespaceMetadataAttrs(
            name='test', value='42', op='delete', namespace='user')])
    api.set_directory_metadata('ifs', metadata=True, directory_metadata=meta)

    # set access control list on a directory
    test_dir = 'ifs/ns_src'
    api.create_directory(
        test_dir, x_isi_ifs_target_type='container',
        x_isi_ifs_access_control='0770')
    print('Directory ACL: {}'.format(api.get_acl(test_dir, acl=True)))

    # give everyone read permissions on the directory
    acl_body = isi_sdk.NamespaceAcl(authoritative='mode', mode='0444')
    api.set_acl(test_dir, acl=True, namespace_acl=acl_body)
    print('Set directory permissions: {}'.format(
        api.get_acl(test_dir, acl=True).mode))
    api.delete_directory(test_dir)

    # build directory query
    query = isi_sdk.DirectoryQuery(
        result=['name', 'size', 'last_modified', 'owner'],
        scope=isi_sdk.DirectoryQueryScope(
            logic='and',
            conditions=[
                isi_sdk.DirectoryQueryScopeConditions(
                    operator='>=',
                    attr='last_modified',
                    value="Thu, 15 Dec 2011 06:41:04"
                ),
                isi_sdk.DirectoryQueryScopeConditions(
                    operator='>=',
                    attr='size',
                    value=1000
                )
            ]
        )
    )
    # exhaustive list of optional details
    details = (
        'access_time,atime_val,block_size,blocks,btime_val,'
        'change_time,create_time,ctime_val,gid,group,id,'
        'is_hidden,mode,mtime_val,nlink,stub,type,uid,'
        'container,container_path')
    # execute directory query
    query_resp = api.query_directory(
        'ifs/data', query=True, directory_query=query, detail=details,
        max_depth=2, limit=2)
    print('Query results for /ifs/data: {}'.format(query_resp))
    print('Successful clean up')


if __name__ == '__main__':
    main()
