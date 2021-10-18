#!/usr/bin/env python
'''
Input: Cluster IP, USERNAME (Optional), Password (Optional)
Output: PAPI_Schemas fetched from cluster. 
Schema file will be created inside /papi_schemas directory with name <OneFS_Relese>.json
Exampple usage:
python generate_PAPIschemas_from_ClusterIP.py -i <CLUSTERIP> -u <CLUSTER_USERNAME> -u <PASSWORD>
'''
from json import JSONEncoder
import argparse
import codecs
from collections import OrderedDict
from copy import deepcopy
import getpass
import json
import logging as log
import os
import requests
import common_resources

requests.packages.urllib3.disable_warnings()

def create_web_session(host, username, password):
    ''' Return a requests.session object with a isi session. '''

    session = requests.Session()

    session.headers['Origin'] = 'https://{}:8080/'.format(host)
    session.headers['Content-Type'] = 'application/json'

    data = {
        'username': username,
        'password': password,
        'services': ['platform', 'namespace']}

    uri = 'https://{}:8080/session/1/session'.format(host)
    response = session.post(uri, json=data, verify=False)

    if response.status_code != requests.codes.CREATED:
        msg = 'Failed to create web session: {}, {}, {}'.format(
            username, response.headers, response.text)
        raise Exception(msg)

    session.headers['X-CSRF-Token'] = session.cookies['isicsrf']

    return session

def requests_with_session(session, url, params = None):
    return session.get(
            url,params=params,
            verify=False).json()

def onefs_release_version(host, port, session):
    """Query a cluster and return the 4 major version digits"""
    url = 'https://{0}:{1}/platform/1/cluster/config'.format(host, port)
    config = requests_with_session(session, url)
    return config['onefs_version']['release'].strip('v')

def onefs_papi_version(host, port, session):
    """Query cluster for latest PAPI version."""
    url = 'https://{0}:{1}/platform/latest'.format(host, port)
    try:
        return requests_with_session(session,url)['latest']
    except KeyError:
        # latest handler did not exist before API version 3
        return '2'

def get_endpoint_paths(source_node_or_cluster, port, base_url, session,
                       exclude_end_points, cached_schemas):
    """
    Gets the full list of PAPI URIs reported by source_node_or_cluster using
    the ?describe&list&json query arguments at the root level.
    Returns the URIs as a list of tuples where collection resources appear as
    (<collection-uri>, <single-item-uri>) and non-collection/static resources
    appear as (<uri>,None).
    """
    desc_list_parms = {'describe': '', 'json': '', 'list': ''}
    url = 'https://' + source_node_or_cluster + ':' + port + base_url
    resp = requests_with_session(
        session, url, params=desc_list_parms)
    end_point_list_json = resp['directory']
    cached_schemas['directory'] = end_point_list_json
        # calls get_endpoint_paths from common_resources
    return common_resources.get_endpoint_paths(end_point_list_json, exclude_end_points)

def main():
    """Main method for create_swagger_config executable."""

    argparser = argparse.ArgumentParser(
        description='Builds Swagger config from PAPI end point descriptions.')
    argparser.add_argument(
        '-i', '--input', dest='host',
        help='IP-address or hostname of OneFS cluster for input',
        action='store', default='localhost')
    argparser.add_argument(
        '-u', '--username', dest='username',
        help='Username for cluster access',
        action='store', default='root')
    argparser.add_argument(
        '-p', '--password', dest='password',
        help='Password for cluster access',
        action='store', default='a')
    argparser.add_argument(
        '-t', '--test', dest='test',
        help='Test mode on', action='store_true', default=False)
    argparser.add_argument(
        '-l', '--logging', dest='log_level',
        help='Logging verbosity level', action='store', default='INFO')
    args = argparser.parse_args()

    log.basicConfig(
        format='%(asctime)s %(levelname)s - %(message)s',
        datefmt='%I:%M:%S', level=getattr(log, args.log_level.upper()))

    schemas_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'papi_schemas'))

    auth = {'username':args.username, 'pwd':args.password}
    base_url = '/platform'
    port = '8080'
    desc_parms = {'describe': '', 'json': ''}

    # Initialize session object and create session if onefs_version is not provided in argumnets
    session = create_web_session(args.host, auth['username'],  auth['pwd']) 
    onefs_version = onefs_release_version(args.host, port, session)
    cached_schemas = {}
    schemas_file = os.path.join(schemas_dir, '{}.json'.format(onefs_version))
    papi_version = int(onefs_papi_version(args.host, port, session))
    
    # invalid backport of handlers caused versioning break
    if papi_version == 5 and onefs_version[:5] == '8.0.1':
        papi_version = 4
    cached_schemas['version'] = papi_version

    if not args.test:
        exclude_end_points = common_resources.get_exclude_endpoints(papi_version)
        end_point_paths = get_endpoint_paths(
            args.host, port, base_url, session, exclude_end_points,
            cached_schemas)
    else:
        exclude_end_points = []

        end_point_paths = [
            ('/1/auth/providers/local', None)
        ]

    success_count = 0
    fail_count = 0

    for base_end_point_path, item_end_point_path in end_point_paths:
        if base_end_point_path is not None:
            log.info('Processing %s', base_end_point_path)
            try:
                url = 'https://{}:{}{}{}'.format(
                    args.host, port, base_url, base_end_point_path)
                base_resp_json = requests_with_session(
                    session, url, params=desc_parms)
                if base_resp_json == None:
                    log.warning('Missing ?describe for API %s', base_end_point_path)
                cached_schemas[base_end_point_path] = deepcopy(base_resp_json) 
                success_count += 1
            except Exception as err:
                log.error('Caught exception while processing: %s. Skipping schema collection for this endpoint', base_end_point_path)
                log.error('%s: %s', type(err).__name__, err)
                fail_count += 1

        if item_end_point_path is not None:
            log.info('Processing %s', item_end_point_path)
            try:
                url = 'https://{}:{}{}{}'.format(
                    args.host, port, base_url, item_end_point_path)
                item_resp_json = requests_with_session(
                    session, url, params=desc_parms)
                if item_resp_json == None:
                    log.warning('Missing ?describe for API %s', item_end_point_path)
                cached_schemas[item_end_point_path] = deepcopy(item_resp_json) 
                success_count += 1
            except Exception as err:
                log.error('Caught exception while processing: %s. Skipping schema collection for this endpoint', item_end_point_path)
                log.error('%s: %s', type(err).__name__, err)
                fail_count += 1
    
    log.info(('Total End points successfully processed: %s, failed to process: %s, '
              'excluded: %s'),
             success_count, fail_count, len(exclude_end_points))
    
    # Put cached_schemas into fle. And store the output file as <OUTPUT>.json inside isilon_sdk/papi_schemas/
    # This overwrites already existing file (if any) from isilon_sdk/papi_schemas/
    with open(schemas_file, 'w+') as schemas:
        schemas.write(json.dumps(
    cached_schemas, sort_keys=True, indent=4,
    separators=(',', ': ')))

if __name__ == '__main__':
    main()