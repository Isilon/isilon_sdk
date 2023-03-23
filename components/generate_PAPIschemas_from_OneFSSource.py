#!/usr/bin/env python3.6
"""
generate_PAPIschemas_from_OneFSSource.py

This script will create <OUTPUT>.json which contains the schema_collection for spcified OneFS source.
json schemas are created by using .json.py scripts in the doc-src subdirectories corresponding to each PAPI handler.

Input parameters:
-s (--source_paths)* : One or more paths for OneFS source dirctory - doc-src e.x(/onefs/isilon/lib/isi_platform_api/doc-src
-i (--include_paths)* : One or more paths for OneFS inclide dirctory - doc-inc, e.x(/onefs/isilon/lib/isi_platform_api/doc-inc
-o (--output)* : Output file name without extension e.x: 9.4.0.0
-p (--papi_version) <Optional>: PAPI Version (Only for excluding endpoints. default 15)
-t (--test) <Optional> : Test mode on
-l (--logging) <Optional> : Logging verbosity level
--debug_build <Optional>: This will cover g_debug endpoints

Output:
<OUTPUT>.json which contains the schema_collection for spcified OneFS source. 
This file will be stored in isilon_sdk/papi_schemas/
We can generate OAS_Schemas by running create_swagger_config.py with parameter --version same as -v used to run this script

Requirements: Need to have OneFS repositary on local machine for providing source paths
Clone from: https://github.west.isilon.com/isilon/onefs/

Example Usage: 
python components/generate_PAPIschemas_from_OneFSSource.py -s /local/home/anaik1/onefs/isilon/lib/isi_platform_api/doc-src /local/home/anaik1/onefs/isilon/lib/isi_celog_api/doc-src 
-i /local/home/anaik1/onefs/isilon/lib/isi_platform_api/doc-inc /local/home/anaik1/onefs/isilon/lib/isi_celog_api/doc-inc -p 15 -o test
"""

import os
import subprocess
import argparse
import json
import logging as log
import re
import common_resources

lst_end_point_paths = []
valid_arg_types = ['GET_args', 'POST_args', 'PUT_args', 'DELETE_args']

def collect_end_points(path, papi_version):
    """
    Function to collect endpoints from doc-src which contains .py files 
    and collect them into endpoint list - lst_end_point_paths
    endpoints - '/[0-9]/local'  are excluded
    """
    for file in os.listdir(path):
        d = os.path.join(path, file)
        if os.path.isdir(d): 
            # Take endpoints having PAPI_version <= papi_version arg for processing
            # float('DOC_SRC/1/audit/topics'.split(DOC_SRC)[1].split('/')[1]) = 1.0
            if float(d.split(DOC_SRC)[1].split('/')[1]) <= papi_version and not (re.findall("[0-9]/local", d)):
                for fname in os.listdir(d):
                    # Valid endpoints have .json.py files like GET_output_schema.json.py, POST_input_schema.json.py, overview.json.py etc. inside doc-src. 
                    # So use only those end points for processing
                    if fname.endswith('.json.py'):
                        # 'DOC_SRC/1/audit/topics'.split('DOC_SRC')[1] = /1/audit/topics
                        lst_end_point_paths.append(d.split(DOC_SRC)[1])
                        break
                collect_end_points(d, papi_version)

def sort_endpoints(e):
    """
    Endpoints should be sorted so that endpoints with different PAPI_versions should be adjacent E.x:
    "/12/upgrade/cluster/upgrade",
    "/3/upgrade/cluster/upgrade",
    "/5/upgrade/cluster/upgrade",
    "/7/upgrade/cluster/upgrade",
    "/9/upgrade/cluster/upgrade",
    """
    return e.split("/",2)[2]

def fetch_schemas(DOC_INC, DOC_SRC, end_point_path='', ERROR_SCHEMAS=None):
    """
    Returns schemas - python dictionary object for the end_point_path by running .json.py files
    This object will be appended in cached_schemas
    """
    path = DOC_SRC + end_point_path
    # Initialising endpoint_schema to collect schemas for different methods for that end_point_path
    endpoint_schema = {}
    endpoint_schema[end_point_path] = {}
    for filename in os.listdir(path):
        file_to_process = os.path.join(path, filename)
        if os.path.isfile(file_to_process) and filename.endswith('.json.py'):
            command_args = ['python', file_to_process]
            schema = subprocess.check_output(command_args, env={'PYTHONPATH': DOC_INC})
            # schema = subprocess.check_output(command_args, env={'PYTHONPATH': '/ifs/home/anaik1/onefs/isilon/lib/isi_platform_api/doc-inc:'+DOC_INC})
            schemas_dict = json.loads(schema)
            # Structuring the schemas for METHOD_[in|out]put_schema.json files. 
            # if filename contains error_schema then no additional structuring required for error_schemas 
            if not 'error_schema' in filename:
                method_schemas = get_method_schemas(end_point_path, filename, schemas_dict, ERROR_SCHEMAS)
                endpoint_schema[end_point_path].update(method_schemas)
            else:
                endpoint_schema = schemas_dict
        # Exceptionally some endpoints have .json files instead of .json.py (e.x - /1/protocols/smb/shares-summary). 
        # Process those endpoints by directly reading .json from file
        elif os.path.isfile(file_to_process) and filename.endswith('.json'):
            with open(file_to_process) as jsonfile:
                schemas_dict = json.load(jsonfile)
                method_schemas = get_method_schemas(end_point_path, filename, schemas_dict, ERROR_SCHEMAS)
                endpoint_schema[end_point_path].update(method_schemas)

    return endpoint_schema

def get_method_schemas(end_point_path, filename, schemas_dict, ERROR_SCHEMAS):
    """
    Structuring the schemas for METHOD_[in|out]put_schema.json files
    """
    schema_type = filename.split('.')[0]
    endpoint_method_schema = {}
    # overview.json.py file contains GET/POST/PUT/DELETE args. 
    # 'resource_description', 'resource_definition' keys from overview.json.py are not required
    if 'overview' in schema_type:
        for arg_type in schemas_dict:
            if arg_type in valid_arg_types:
                endpoint_method_schema[arg_type] = schemas_dict[arg_type]
    elif 'output' in schema_type:
        # For output schemas there is ERROR_SCHEMAS are added as 1st element of type[]
        endpoint_method_schema[schema_type] = {}
        endpoint_method_schema[schema_type]['type'] = [ERROR_SCHEMAS, schemas_dict]
    elif 'input' in schema_type:
        endpoint_method_schema[schema_type] = schemas_dict
        
    return endpoint_method_schema

def main():
    """
    Main method for generate_PAPIschemas_from_OneFSSurce.py
    """
    argparser = argparse.ArgumentParser(description='Generate PAPI schemas from OneFS source')
    argparser.add_argument(
        '-s', '--source_paths', dest='source_paths', nargs='+', default=[], required=True,
        help='One or more paths for OneFS source dirctory - doc-src e.x(/onefs/isilon/lib/isi_platform_api/doc-src')
    argparser.add_argument(
        '-i', '--include_paths', dest='include_paths', nargs='+', default=[], required=True,
        help='One or more paths for OneFS include dirctory - doc-inc, e.x(/onefs/isilon/lib/isi_platform_api/doc-inc')
    argparser.add_argument(
        '-o', '--output', dest='output', required=True,
        help='Output file name without extension',
        action='store', default=None)
    argparser.add_argument(
        '-p', '--papi_version', dest='papi_version',type=int,
        help='PAPI Version (latest 15)',action='store', default="15")
    argparser.add_argument(
        '-t', '--test', dest='test',
        help='Test mode on', action='store_true', default=False)
    argparser.add_argument(
        '-l', '--logging', dest='log_level',
        help='Logging verbosity level', action='store', default='INFO')
    argparser.add_argument(
        '--debug_build', dest='debug_build',
        help='This will cover g_debug endpoints', action='store_true', default=False)
    args = argparser.parse_args()

    # Log Configuration
    log.basicConfig(
        format='%(asctime)s %(levelname)s - %(message)s',
        datefmt='%I:%M:%S', level=getattr(log, args.log_level.upper()))
    
    papi_schema_file = args.output
    papi_version = args.papi_version
    source_paths = args.source_paths
    include_paths = args.include_paths
    for inc_path in include_paths:
        if not os.path.exists(inc_path):
            raise RuntimeError('Invalid INCLUDE_PATH argument: {}'.format(inc_path))
    
    # /doc-inc will be used as PYTHONPATH for running .json.py files from doc-src     
    DOC_INC = ':'.join(include_paths)

    # Test Mode API-Endpoint is taken from Source path /isi_platform_API.
    # So to work with test mode, it is expecetd to have source as /isi_platform_API/doc-src
    if (args.test and len(source_paths)>=1 and '/isi_platform_api' not in source_paths[0]):
        log.warning('Currently test mode works with single source having "/isi_platform_api/doc-src" path')
        exit()

    success_count = 0
    fail_count = 0
    exclude_count = 0
    cached_schemas = {}
    cached_schemas['directory'] = []

    # For multiple OneFS source paths
    for src_path in source_paths:    

        #Path Validation
        if not os.path.exists(src_path):
            raise RuntimeError('Invalid SOURCE_PATH argument: {}'.format(src_path))
        if 'doc-src' not in src_path:
            raise RuntimeError('Invalid SOURCE_PATH argument: {}'.format(src_path))

        if src_path[-1] == '/':
            # Neglect last '/' from path. It is taken care for subdirectories
            src_path = src_path[:-1]

        # source path for end_points -> /doc-src
        global DOC_SRC
        DOC_SRC = src_path

        # This will collect Endpoints in list - lst_end_point_paths after traversing doc-src directory
        collect_end_points(DOC_SRC, papi_version)
        # Sort the endpoints by keeping same endpoints with different PAPI Versions adjacent
        lst_end_point_paths.sort(key=sort_endpoints)
        log.info(('Started processing endpoints from path - %s'),
                src_path)
        # Collect the valid end_point_paths from common_resources for further processing
        if not args.test:
            exclude_end_points = common_resources.get_exclude_endpoints(papi_version)
            # If debugbuild is false then exclude debugbuild endpoints
            if not args.debug_build:
                exclude_end_points.extend(common_resources.debug_build_exclusion_list)
            end_point_paths = common_resources.get_endpoint_paths(lst_end_point_paths, exclude_end_points)
        else:
            exclude_end_points = []

            end_point_paths = [
                ('/1/audit/topics', None)
            ]

        log.info(('End points collected from %s/doc-src : %s'),
                src_path, len(lst_end_point_paths))

        ERROR_SCHEMAS = fetch_schemas(DOC_INC, DOC_SRC)
        
        # Loop through end_point_paths and append the collected schemas in cached_schemas
        for base_end_point_path, item_end_point_path in end_point_paths:
            if base_end_point_path is not None:
                log.info('Processing %s', base_end_point_path)
                try:
                    endpoint_schema = fetch_schemas(DOC_INC, DOC_SRC, base_end_point_path, ERROR_SCHEMAS)
                    cached_schemas.update(endpoint_schema)
                    success_count += 1
                except Exception as err:
                    log.error('Caught exception while processing: %s. Skipping schema collection for this endpoint', base_end_point_path)
                    log.error('%s: %s', type(err).__name__, err)
                    lst_end_point_paths.remove(base_end_point_path)
                    fail_count += 1

            if item_end_point_path is not None:
                log.info('Processing %s', item_end_point_path)
                try:
                    endpoint_schema = fetch_schemas(DOC_INC, DOC_SRC, item_end_point_path, ERROR_SCHEMAS)
                    cached_schemas.update(endpoint_schema)
                    success_count += 1
                except Exception as err:
                    log.error('Caught exception while processing: %s. Skipping schema collection for this endpoint', item_end_point_path)
                    log.error('%s: %s', type(err).__name__, err)
                    lst_end_point_paths.remove(item_end_point_path)
                    fail_count += 1

        log.info(('Completed processing end points from path - %s'),
                src_path)
        # Excluded end-point should always be removed from cached_schemas['directory']
        lst_filtered_end_point_paths = []
        for ep in lst_end_point_paths:
            if ep not in exclude_end_points:
                lst_filtered_end_point_paths.append(ep)
            else:
                exclude_count += 1
        cached_schemas['directory'].extend(lst_filtered_end_point_paths)
        del lst_end_point_paths[:]

    cached_schemas['version'] = papi_version
    
    log.info(('Total End points successfully processed: %s, failed to process: %s, '
              'excluded: %s'),
             success_count, fail_count, exclude_count)
    
    # Put cached_schemas into fle. And store the output file as <OUTPUT>.json inside isilon_sdk/papi_schemas/
    # This overwrites already existing file (if any) from isilon_sdk/papi_schemas/
    schemas_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'papi_schemas'))
    schemas_file = os.path.join(schemas_dir, '{}.json'.format(papi_schema_file))
    with open(schemas_file, 'w+') as schemas:
        schemas.write(json.dumps(
    cached_schemas, sort_keys=True, indent=4,
    separators=(',', ': ')))

if __name__ == '__main__':
    main()
