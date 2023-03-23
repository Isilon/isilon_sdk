"""
common_resources.py
This file contains common resources utilised by;
1) create_swagger_config.py
2) generateschemas_from_OneFSSource.py
"""

"""
Future plan - Exclude endpoint list should be dynamic
"""

debug_build_exclusion_list = [
    '/1/versiontest/automatic',
    '/2/versiontest/automatic',
    '/5/esrs/settings',
    '/11/esrs/settings',
    '/10/sample/settings',
    '/10/sample/multijobaction',
    '/10/sample/multijobaction/<JOB>',
    '/10/sample/commandpattern'
]

def get_exclude_endpoints(papi_version):
    exclude_end_points = [
                # Endpoints having unsupported_overview in overview.json.py
                '/1/cluster_test_simple',
                '/1/cluster_test_token/<ID>',
                '/1/cluster_test_token2/<ID>/details',
                '/1/isivc/task/<TASKID*>',
                '/1/sra/failover',
                '/1/sra/scheduler/<POLICYID>',
                '/1/sra/scheduler',
                '/1/sra/source/policies',
                '/1/sra/source/policy',
                '/1/sra/syncoperations/policy/<PID>/job_guid/<JGUID>/job_id/<JID>',
                '/1/sra/syncoperations',
                '/1/sra/target/policies',
                '/1/block/targets',
                '/1/block/targets/<TARGET-NAME>',
                '/1/block/targets/<TARGET-NAME>/logicalunits',
                '/1/block/targets/<TARGET-NAME>/logicalunits/<LUN>',
                '/1/diskpool/diskpools',
                '/1/diskpool/diskpools/<NAME>',
                '/1/diskpool/nodemap',
                '/1/local/cluster_test_simple',
                '/1/local/cluster_test_token/<ID>',
                '/1/local/cluster_test_token2/<ID>/details',
                '/1/sra/syncoperations/policy/<PID>',
                '/1/sra/target/policy',

                # Endpoints with get/put/post args in overview doc but no equivalent schemas
                '/1/diskpool/3/librarytest/example',
                '/1/storagepool/compatibilities/class/active',
                '/1/storagepool/compatibilities/class/active/<ID>',
                '/1/storagepool/compatibilities/class/available',
                '/1/storagepool/compatibilities/ssd/available',
                '/1/storagepool/compatibilities/ssd/active/<ID>',
                '/3/storagepool/compatibilities/ssd/active/<ID>',
                '/1/storagepool/compatibilities/ssd/active',
                '/3/storagepool/compatibilities/ssd/active',
                '/3/local/hardware/fcports',
                '/3/network/actions',
                '/5/upgrade/hardware/start',
                '/5/upgrade/hardware/status',
                '/5/upgrade/hardware/stop',

                # Internal endpoints (endpoints observed with internal true)
                '/1/sync/events',
                '/1/vonefs/config',
                '/1/network/membership',
                '/1/test/serializer/semaphore',
                '/3/iiq/instances',
                '/3/iiq/instances/<IIQ_IP>',
                '/3/cluster/config/join-mode',
                '/3/sync/settings/advanced',
                '/3/network/membership',
                '/3/statistics/verification_info',
                '/4/id-resolution/paths',
                '/4/id-resolution/paths/<LIN>',
                '/4/local/upgrade/cluster/nodes/<LNN>/patch/sync',
                '/7/sync/settings/advanced',
                '/10/cluster/brand',
                '/14/cluster-mode',
                '/14/local/cluster/internal-networks/preferred-network',
                '/16/local/os/security'
                ]
    if papi_version < 3:
            exclude_end_points.extend([
                '/1/cluster/external-ips',
                '/1/debug/echo/<TOKEN>',
                '/1/event/events',
                '/1/event/events/<ID>',
                '/1/fsa/path',
                '/1/license/eula',
                '/1/protocols/nfs/aliases',
                '/1/protocols/nfs/aliases/<AID>',
                '/1/protocols/nfs/check',
                '/1/protocols/nfs/exports',
                '/1/protocols/nfs/exports-summary',
                '/1/protocols/nfs/exports/<EID>',
                '/1/protocols/nfs/nlm/locks',
                '/1/protocols/nfs/nlm/sessions',
                '/1/protocols/nfs/nlm/sessions/<ID>',
                '/1/protocols/nfs/nlm/waiters',
                '/1/protocols/nfs/reload',
                '/1/protocols/nfs/settings/export',
                '/1/protocols/nfs/settings/global',
                '/1/protocols/nfs/settings/zone'
            ])
    else:
            exclude_end_points.extend([
                '/1/auth/users/<USER>/change_password',
                # use /3/auth/users/<USER>/change-password instead
                '/1/auth/users/<USER>/member_of',
                '/1/auth/users/<USER>/member_of/<MEMBER_OF>',
                # use /3/auth/users/<USER>/member-of instead
                '/1/debug/echo/<TOKEN>',
                '/1/debug/echo/<LNN>/<TOKEN>',
                '/1/fsa/path',
                '/1/license/eula',
                '/1/local/debug/echo/<LNN>/<TOKEN>',
                '/1/storagepool/suggested_protection/<NID>',
                # use /3/storagepool/suggested-protection/<NID> instead
                '/3/cluster/email/default-template',
                '/3/local/cluster/version',
                # ?describe output missing for endpoint
                '/11/local/avscan/nodes/<LNN>/status'
            ])
    return exclude_end_points

def get_endpoint_paths(end_point_list, exclude_end_points):
    """
    Gets the full list of PAPI URIs reported by source_node_or_cluster using
    the ?describe&list&json query arguments at the root level.
    Returns the URIs as a list of tuples where collection resources appear as
    (<collection-uri>, <single-item-uri>) and non-collection/static resources
    appear as (<uri>,None).
    """
    
    end_point_list_json = end_point_list
        
    base_end_points = {}
    end_point_paths = []
    ep_index = 0
    num_endpoints = len(end_point_list_json)
    while ep_index < num_endpoints:
        current_endpoint = end_point_list_json[ep_index]
        current_endpoint_version = current_endpoint.split('/', 2)[1]
        if current_endpoint_version.find('.') != -1:
            # skip floating point version numbers
            ep_index += 1
            continue

        next_ep_index = ep_index + 1
        while next_ep_index < num_endpoints:
            current_endpoint = end_point_list_json[ep_index]
            current_endpoint_version = current_endpoint.split('/', 2)[1]
            next_endpoint = end_point_list_json[next_ep_index]
            # strip off the version and compare to see if they are
            # the same.
            if (next_endpoint.split('/', 2)[-1] !=
                    current_endpoint.split('/', 2)[-1]):
                # using current_endpoint
                break
            # skipping current_endpoint
            next_endpoint_version = next_endpoint.split('/', 2)[1]
            if next_endpoint_version.find('.') == -1:

                if (int(current_endpoint_version) > int(next_endpoint_version)):
                    # swap the values, put the higher version down in the list
                    end_point_list_json[ep_index] = next_endpoint
                    end_point_list_json[ep_index + 1] = current_endpoint
            else:
                # leave the x.x values
                end_point_list_json[ep_index] = next_endpoint
                end_point_list_json[ep_index + 1] = current_endpoint

            ep_index = next_ep_index
            next_ep_index += 1
            ##This is the last endpoint so utilize the max version
            if next_ep_index == num_endpoints:
                current_endpoint = end_point_list_json[ep_index]

        if current_endpoint in exclude_end_points:
            ep_index += 1
            continue

        if current_endpoint[-1] != '>':
            base_uri = current_endpoint.split('/', 2)[2]
            base_end_points[base_uri] = (current_endpoint, None)
        else:
            try:
                item_endpoint = current_endpoint.split('/', 2)[2]
                last_slash = item_endpoint.rfind('/')
                base_end_point_tuple = \
                    base_end_points[item_endpoint[0:last_slash]]
                base_end_point_tuple = (base_end_point_tuple[0], current_endpoint)
                end_point_paths.append(base_end_point_tuple)
                del base_end_points[item_endpoint[0:last_slash]]
            except KeyError:
                # no base for this item_endpoint
                end_point_paths.append((None, current_endpoint))

        ep_index += 1

    # remaining base end points have no item end point
    for base_end_point_tuple in list(base_end_points.values()):
        end_point_paths.append(base_end_point_tuple)
    def cmp_to_key(mycmp):
       class K(object):
         def __init__(self, obj, *args):
            self.obj = obj
         def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
         def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
         def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
         def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
         def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
         def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
       return K
    def cmp(a, b):
        return (a > b) - (a < b)
    def end_point_path_compare(a, b):
        """Compare two endpoints.
        Return value is negative if a < b,
        Return value is zero if a == b
        Return value is positive if a > b.
        """
        lhs = a[0]
        if lhs is None:
            lhs = a[1]
        rhs = b[0]
        if rhs is None:
            rhs = b[1]
        if lhs.find(rhs) == 0 or rhs.find(lhs) == 0:
            return len(rhs) - len(lhs)

        return cmp(lhs, rhs)

    return sorted(end_point_paths ,key=cmp_to_key(end_point_path_compare))
