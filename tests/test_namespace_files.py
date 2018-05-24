"""Files with isi_sdk.NamespaceApi."""
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

    # create a file
    contents = 'Lorem ipsum dolor sit amet, est eu nobis volutpat maluisset.'
    api.create_file(
        'ifs/data/lorem', x_isi_ifs_target_type='object',
        file_contents=contents, x_isi_ifs_access_control='600')
    # fetch file contents
    print('File contents: {}'.format(api.get_file_contents('ifs/data/lorem')))

    # copy file /ifs/data/lorem to /ifs/data/ipsum
    api.copy_file(
        'ifs/data/ipsum', x_isi_ifs_copy_source='/namespace/ifs/data/lorem')
    api.delete_file('ifs/data/ipsum')

    # clone file /ifs/data/lorem to /ifs/data/ipsum
    api.copy_file(
        'ifs/data/ipsum', x_isi_ifs_copy_source='/namespace/ifs/data/lorem',
        clone=True, overwrite=True)
    api.delete_file('ifs/data/ipsum')

    # move file /ifs/data/lorem to /ifs/data/ipsum
    api.move_file(
        'ifs/data/lorem', x_isi_ifs_set_location='/namespace/ifs/data/ipsum')

    # set extended attribute on a file
    print(api.get_file_metadata('ifs/data/ipsum', metadata=True))

    # create extended attribute
    meta = isi_sdk.NamespaceMetadata(
        action='update',
        attrs=[isi_sdk.NamespaceMetadataAttrs(
            name='test', value='42', op='update', namespace='user')])
    api.set_file_metadata(
        'ifs/data/ipsum', metadata=True, file_metadata=meta)

    # assert that extended attribute value was set
    for attr in api.get_file_metadata(
            'ifs/data/ipsum', metadata=True).attrs:
        if attr.name == 'test':
            print('Extended attribute was set: {}'.format(attr.value == '42'))

    attrs = api.get_file_attributes_with_http_info('ifs/data/ipsum')
    # the third index of the response is the response headers
    print('File attribute headers: {}'.format(attrs[2]))
    api.delete_file('ifs/data/ipsum')

    # set access control list on a file
    api.create_file(
        'ifs/data/lorem', x_isi_ifs_target_type='object',
        x_isi_ifs_access_control='private_read',
        file_contents='Lorem ipsum dolor sit amet.')

    # get current file permissions
    acl = api.get_acl('ifs/data/lorem', acl=True)
    print('ACL mode is {}'.format(acl.mode))

    # modify file permissions
    acl_body = isi_sdk.NamespaceAcl(authoritative='mode', mode='0555')
    api.set_acl('ifs/data/lorem', acl=True, namespace_acl=acl_body)
    acl = api.get_acl('ifs/data/lorem', acl=True)
    print('New ACL mode is {}'.format(acl.mode))

    api.delete_file('ifs/data/lorem')
    print('Successful clean up')


if __name__ == '__main__':
    main()
