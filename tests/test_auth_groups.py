import isi_sdk
import urllib3

urllib3.disable_warnings()
# configure username and password
isi_sdk.configuration.username = "root"
isi_sdk.configuration.password = "a"
isi_sdk.configuration.verify_ssl = False

# configure host
host = "https://VNODE2294.west.isilon.com:8080"
apiClient = isi_sdk.ApiClient(host)
authApi = isi_sdk.AuthApi(apiClient)

newAuthGroup = isi_sdk.AuthGroupCreateParams()
newAuthGroup.name = "alex"

print "Creating group " + newAuthGroup.name
createAuthGroupResp = authApi.create_auth_group(newAuthGroup)

print "Created: " + str(createAuthGroupResp)

authGroups = authApi.list_auth_groups()

foundNewGroup = False
for group in authGroups.groups:
    if group.name == newAuthGroup.name:
        foundNewGroup = True

print "Found it: " + str(foundNewGroup)

authGroups = authApi.get_auth_group(auth_group_id=newAuthGroup.name)

foundNewGroup = False
for group in authGroups.groups:
    if group.name == newAuthGroup.name:
        foundNewGroup = True

print "Found it again: " + str(foundNewGroup)

updateAuthGroup = isi_sdk.AuthGroup()
# The only updatable value according to the description is the gid, but when i
# try to change it, the response is that i need to include a force parameter,
# but there is no force parameter in the description. Seems like a bug.
authApi.update_auth_group(auth_group_id=newAuthGroup.name,
                          auth_group=updateAuthGroup)

# try adding a member
groupMember = isi_sdk.GroupsGroupMember()
groupMember.name = "admin"
groupMember.type = "user"

authApi.create_groups_group_member(group=newAuthGroup.name,
                                   groups_group_member=groupMember)

groupMembers = authApi.list_groups_group_members(group=newAuthGroup.name)
foundMember = False
for member in groupMembers.members:
    if member.name == groupMember.name:
        foundMember = True

print "Found member: " + str(foundMember)

# delete the member
authApi.delete_groups_group_member(group=newAuthGroup.name,
                                   groups_group_member_id=groupMembers.members[0].id)

groupMembers = authApi.list_groups_group_members(group=newAuthGroup.name)
foundMember = False
for member in groupMembers.members:
    if member.name == groupMember.name:
        foundMember = True

print "Deleted member: " + str(foundMember == False)

authApi.delete_auth_group(newAuthGroup.name)

authGroups = authApi.list_auth_groups()
foundNewGroup = False
for group in authGroups.groups:
    if group.name == newAuthGroup.name:
        foundNewGroup = True

print "Deleted it: " + str(foundNewGroup == False)

print "Done."
