import json
import urllib3

import isi_sdk_8_0 as isi_sdk

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
    auth_api = isi_sdk.AuthApi(api_client)

    new_auth_group = isi_sdk.AuthGroupCreateParams(name='admins')

    print("Creating group %s" % new_auth_group.name)
    try:
        create_auth_group_resp = auth_api.create_auth_group(new_auth_group)
        print("Created: %s" % create_auth_group_resp.id)
    except isi_sdk.rest.ApiException as err:
        if err.status == 409:
            print("Group %s already exists" % new_auth_group.name)
        else:
            raise err

    auth_groups = auth_api.list_auth_groups()

    found_new_group = False
    for group in auth_groups.groups:
        if group.name == new_auth_group.name:
            found_new_group = True

    print("Found it: " + str(found_new_group))

    auth_groups = auth_api.get_auth_group(auth_group_id=new_auth_group.name)

    found_new_group = False
    for group in auth_groups.groups:
        if group.name == new_auth_group.name:
            found_new_group = True

    print("Found it again: " + str(found_new_group))

    auth_group = isi_sdk.AuthGroup()
    # The only updatable value according to the description is the gid, but when i
    # try to change it, the response is that I need to include a force parameter,
    # but there is no force parameter in the description. Seems like a bug.
    auth_api.update_auth_group(auth_group_id=new_auth_group.name,
                               auth_group=auth_group)

    # try adding a member
    group_member = isi_sdk.GroupMember(name='admin', type='user')

    auth_groups_api = isi_sdk.AuthGroupsApi(api_client)
    try:
        auth_groups_api.create_group_member(
            group=new_auth_group.name, group_member=group_member)
    except isi_sdk.rest.ApiException as err:
        body = json.loads(err.body)
        if 'User is already in local group' in body['errors'][0]['message']:
            print('User %s is already in local group' % group_member.name)
        else:
            raise err
    except ValueError as err:
        print('Resource ID was not returned in response')

    group_members = auth_groups_api.list_group_members(group=new_auth_group.name)
    found_member = False
    for member in group_members.members:
        if member.name == group_member.name:
            found_member = True

    print("Found member: " + str(found_member))

    # delete the member
    auth_groups_api.delete_group_member(
        group=new_auth_group.name, group_member_id=group_members.members[0].id)

    group_members = auth_groups_api.list_group_members(group=new_auth_group.name)
    found_member = False
    for member in group_members.members:
        if member.name == group_member.name:
            found_member = True

    print("Deleted member: " + str(found_member == False))

    auth_api.delete_auth_group(new_auth_group.name)

    auth_groups = auth_api.list_auth_groups()
    found_new_group = False
    for group in auth_groups.groups:
        if group.name == new_auth_group.name:
            found_new_group = True

    print("Deleted it: " + str(found_new_group == False))

    print("Done.")


if __name__ == '__main__':
    main()
