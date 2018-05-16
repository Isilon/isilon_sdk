"""Access points with isi_sdk.NamespaceApi."""
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
    auth_api = isi_sdk.AuthApi(api_client)

    # get list of access points
    print('Access points: {}'.format(api.list_access_points().namespaces))

    # get list of access point versions
    versions = api.list_access_points(versions=True).versions
    print('Protocol versions of namespace access server: {}'.format(versions))

    # create access point
    ap_path = isi_sdk.AccessPointCreateParams(path='/ifs/home')
    api.create_access_point('user1', access_point=ap_path)
    print('Access points: {}'.format(api.list_access_points().namespaces))

    # create test user
    auth_user = isi_sdk.AuthUserCreateParams(
        name='user1', password='user1', home_directory='/ifs/home/user1')
    auth_api.create_auth_user(auth_user)

    # set ACL for user
    acl_body = isi_sdk.NamespaceAcl(
        authoritative='acl',
        acl=[
            isi_sdk.AclObject(
                trustee={'name': 'user1', 'type': 'user'},
                accesstype='allow',
                accessrights=['file_read'],
                op='add'
            )
        ]
    )
    api.set_acl('user1', acl=True, nsaccess=True, namespace_acl=acl_body)

    # get access control list
    print('ACL: {}'.format(api.get_acl('user1', acl=True, nsaccess=True)))

    # clean up test access point
    api.delete_access_point('user1')
    # clean up test user
    auth_api.delete_auth_user('user1')
    api.delete_directory('ifs/home/user1', recursive=True)
    print('Successful clean up')


if __name__ == '__main__':
    main()
