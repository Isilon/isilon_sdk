#!/usr/bin/env python3.6
"""
This script will print to stdout a swagger config based on the ?describe
responses from the PAPI handlers on your cluster (specified by cluster name or
ip address as the first argument to this script).  Swagger tools can now use
this config to create language bindings and documentation.
"""
from json import JSONEncoder
import argparse
try:
    import builtins
except ImportError:
    import __builtin__ as builtins
import codecs
from collections import OrderedDict
from copy import deepcopy
import getpass
import json
import logging as log
import os
import re
import sys
import traceback
import requests
from requests.auth import HTTPBasicAuth
import common_resources

requests.packages.urllib3.disable_warnings()

SWAGGER_PARAM_ISI_PROP_COMMON_FIELDS = [
    'description', 'required', 'type', 'default', 'maximum', 'minimum', 'enum',
    'items', 'maxLength', 'minLength', 'pattern']

NON_REQUIRED_PROPS = {
    'StatisticsCurrentStat': ['value'],
    'SummaryClientClientItem': ['node'],
    'SummaryHeatHeatItem': ['event_type', 'lin', 'node'],
    'SummaryProtocolProtocolItem': ['node'],
    'SummarySystemSystemItem': ['iscsi'],
    'QuotaQuota': ['description', 'labels'],
}

MISSING_POST_RESPONSE = {
    '/1/protocols/hdfs/proxyusers/<NAME>/members',
    '/3/protocols/ntp/servers',
    '/3/protocols/swift/accounts'
}

# list of url parameters that need to be url encoded, this hack works for now,
# but could cause problems if new params are added that are not unique.
URL_ENCODE_PARAMS = ['NfsAliasId']
# our extension to swagger which is used to generate code for doing the url
# encoding of the parameters specified above.
X_ISI_URL_ENCODE_PATH_PARAM = 'x-isi-url-encode-path-param'

# our custom json schema keyword
X_SENSITIVE = 'x-sensitive'

# tracks swagger operations generated from URLs to ensure uniqueness
GENERATED_OPS = {}
SWAGGER_DEFS = {}

MAX_ARRAY_SIZE = 2147483642
MAX_STRING_SIZE = 2147483647
MAX_INTEGER_SIZE = 9223372036854775807

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


def isi_props_to_swagger_params(isi_props, param_type):
    """Convert isi properties to Swagger parameters."""
    if not isi_props:
        return []
    swagger_parameters = []
    for isi_prop_name, isi_prop in list(isi_props.items()):
        # build a swagger param for each isi property
        swagger_param = {}
        swagger_param['in'] = param_type
        swagger_param['name'] = isi_prop_name
        # attach common fields
        for field_name in isi_prop:
            if field_name not in SWAGGER_PARAM_ISI_PROP_COMMON_FIELDS:
                log.warning('%s not defined for Swagger in prop: %s',
                            field_name, isi_prop)
                continue
            if field_name == 'type':
                if isi_prop[field_name] == 'int':
                    log.warning('Invalid type in params of type %s: %s',
                                param_type, isi_props)
                    isi_prop[field_name] = 'integer'
                elif isi_prop[field_name] == 'bool':
                    log.warning('Invalid type in params of type %s: %s',
                                param_type, isi_props)
                    isi_prop[field_name] = 'boolean'
            swagger_param[field_name] = isi_prop[field_name]
        # add the new param to the list of params
        swagger_parameters.append(swagger_param)
    return swagger_parameters


class PostFixUsed(object):
    """Class to enable passing a boolean by reference."""
    flag = False


def plural_obj_name_to_singular(obj_name, post_fix='', post_fix_used=None):
    """Convert plural object name to a singular name."""
    acronyms = ['Ads', 'Nis']  # list of acronyms that end in 's'
    # if it's two 'ss' on the end then don't remove the last one
    if (obj_name not in acronyms and obj_name[-1] == 's' and
            obj_name[-2] != 's' and not obj_name.endswith('tus')):
        # if container object ends with 's' then trim off the 's'
        # to (hopefully) create the singular version
        if obj_name[-3:] == 'ies':
            one_obj_name = obj_name[:-3].replace('_', '') + 'y'
        elif obj_name[-4:] == 'ches' or obj_name[-5:] == 'iases':
            one_obj_name = obj_name[:-2].replace('_', '')
        else:
            one_obj_name = obj_name[:-1].replace('_', '')
    else:
        one_obj_name = obj_name.replace('_', '') + post_fix
        if post_fix_used is not None:
            post_fix_used.flag = True

    return one_obj_name


def find_best_type_for_prop(prop):
    """Find best type match for property."""
    multiple_types = prop['type']
    # delete it so that we throw an exception if none of types
    # are non-'null'
    del prop['type']

    for one_type in multiple_types:
        # sometimes the types are base types and sometimes they
        # are sub objects
        if isinstance(one_type, dict):
            if one_type['type'] == 'null':
                continue

            # favor more specific types over 'string'
            if isinstance(one_type['type'], list):
                one_type = find_best_type_for_prop(one_type)

            prop = one_type
            if prop['type'] != 'string':
                break

        elif one_type != 'null':
            prop['type'] = one_type
            # prefer arrays first and strings second because all properties
            # with an array type should also have an items field defined
            if one_type == 'array' or (one_type == 'string' and
                                       'items' not in prop):
                break

    # multi-types cannot be restricted by a string enum
    if prop['type'] == 'string' and 'enum' in prop:
        del prop['enum']

    return prop


def isi_to_swagger_array_prop(prop, prop_name, isi_obj_name,
                              isi_obj_name_space, isi_schema_props,
                              class_ext_post_fix, is_response_object):
    """Convert isi array property to Swagger array property."""

    if 'items' not in prop:
        log.warning("Missing 'items' field in '%s' property", prop_name)
        if 'item' in prop:
            prop['items'] = prop['item']
            del prop['item']
        else:
            # default to string if not defined
            prop['items'] = {'type': 'string'}

    # protect against Java array out of bounds exception
    # TODO: We can remove this check when sdk build is
    # integrated with Jenkins
    # if 'maxItems' in prop and prop['maxItems'] > MAX_ARRAY_SIZE:
    if 'maxItems' in prop:
        del prop['maxItems']

    if 'type' not in prop['items'] and prop['items'] == 'string':
        prop['items'] = {'type': 'string'}
        log.warning("Found 'string' as 'items' object value")
    elif 'type' not in prop['items'] and prop['items'] == 'integer':
        prop['items'] = {'type': 'integer'}
        log.warning("Found 'integer' as 'items' object value")
    elif (('type' not in prop['items'] and isinstance(prop['items'], dict)) or
          ('type' in prop['items'] and prop['items']['type'] == 'object')):
        items_obj_name = plural_obj_name_to_singular(prop_name.title(),
                                                     post_fix='Item')
        if 'type' not in prop['items']:
            log.warning("Missing 'object' type in '%s'", prop_name)
        if (items_obj_name == isi_obj_name or
                items_obj_name == plural_obj_name_to_singular(isi_obj_name)):
            # HACK don't duplicate the object name if the singular version of
            # this property is the same as the singular version of the
            # object name.
            items_obj_namespace = isi_obj_name_space
        else:
            items_obj_namespace = isi_obj_name_space + isi_obj_name
        # store the description in the ref for property object refs
        if 'description' in prop['items']:
            prop_description = prop['items']['description']
            del prop['items']['description']
        else:
            prop_description = ''

        obj_ref = isi_schema_to_swagger_object(
            items_obj_namespace, items_obj_name, prop['items'],
            class_ext_post_fix, is_response_object)
        isi_schema_props[prop_name]['items'] = {
            'description': prop_description, '$ref': obj_ref}
    elif ('type' in prop['items'] and
          isinstance(prop['items']['type'], dict) and
          'type' in prop['items']['type'] and
          prop['items']['type']['type'] == 'object'):

        items_obj_name = plural_obj_name_to_singular(
            prop_name.title(), post_fix='Item')
        if (items_obj_name == isi_obj_name or
                items_obj_name == plural_obj_name_to_singular(isi_obj_name)):
            # HACK don't duplicate the object name if the singular version of
            # this property is the same as the singular version of the
            # object name.
            items_obj_namespace = isi_obj_name_space
        else:
            items_obj_namespace = isi_obj_name_space + isi_obj_name
        # store the description in the ref for property object refs
        obj_ref = isi_schema_to_swagger_object(
            items_obj_namespace, items_obj_name, prop['items']['type'],
            class_ext_post_fix, is_response_object)
        isi_schema_props[prop_name]['items'] = {'$ref': obj_ref}
    elif ('type' in prop['items'] and
          isinstance(prop['items']['type'], list)):
        prop['items'] = find_best_type_for_prop(prop['items'])
        isi_schema_props[prop_name]['items'] = prop['items']
    elif 'type' in prop['items'] and prop['items']['type'] == 'array':
        isi_to_swagger_array_prop(
            prop['items'], 'items', isi_obj_name, isi_obj_name_space,
            isi_schema_props[prop_name], class_ext_post_fix,
            is_response_object)
    elif 'type' in prop['items']:
        if prop['items']['type'] == 'any' or prop['items']['type'] == 'string':
            # Swagger does not support 'any'
            if prop['items']['type'] == 'any':
                prop['items']['type'] = 'string'
            # the custom added keyword 'x-sensitive' is custom, not
            # recognized by swagger, and needs to be removed from arrays
            # this keyword will only exist where prop type is a string
            if X_SENSITIVE in prop['items']:
                del prop['items'][X_SENSITIVE]
        elif prop['items']['type'] == 'int':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['items']['type'] = 'integer'
        elif prop['items']['type'] == 'bool':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['items']['type'] = 'boolean'
    elif 'type' not in prop['items'] and '$ref' not in prop['items']:
        raise RuntimeError("Array with no type or $ref: {}".format(prop))


def isi_schema_to_swagger_object(isi_obj_name_space, isi_obj_name,
                                 isi_schema, class_ext_post_fix,
                                 is_response_object=False):
    """Convert isi_schema to Swagger object definition."""

    # Converts to a single schema with '#ref' for sub-objects
    # which is what Swagger expects. Adds the sub-objects
    # to the SWAGGER_DEFS dictionary.
    if 'type' not in isi_schema:
        # have seen this for empty responses
        if 'properties' not in isi_schema and 'settings' not in isi_schema:
            log.warning(('Invalid empty schema for object %s. '
                         "Adding 'properties' and 'type'."), isi_obj_name)
            isi_schema = {'properties': isi_schema}
        else:
            log.warning(("Invalid schema for object %s, no 'type' specified. "
                         "Adding 'type': 'object'."), isi_obj_name)
        isi_schema['type'] = 'object'

    if isinstance(isi_schema['type'], list):
        for schema_list_item in isi_schema['type']:
            if schema_list_item is None:
                log.warning("Found null object in JSON schema list")
            elif 'type' not in schema_list_item:
                return '#/definitions/Empty'
            elif schema_list_item['type'] == 'object':
                isi_schema = schema_list_item
                break

    if isi_schema['type'] != 'object':
        raise RuntimeError("isi_schema is not type 'object': {}".format(
            isi_schema))

    # found a few empty objects that omit the properties field
    if 'properties' not in isi_schema:
        log.warning("Missing 'properties' object")
        if 'settings' in isi_schema:
            if ('type' in isi_schema['settings'] and
                    isi_schema['settings']['type'] == 'object' and
                    'properties' in isi_schema['settings']):
                # saw this with /3/protocols/nfs/netgroup
                isi_schema['properties'] = {'settings': isi_schema['settings']}
            else:
                # saw this with /3/cluster/timezone
                isi_schema['properties'] = {
                    'settings': {
                        'properties': isi_schema['settings'],
                        'type': 'object'
                    }
                }
            del isi_schema['settings']
        else:
            isi_schema['properties'] = {}

    sub_obj_namespace = isi_obj_name_space + isi_obj_name
    required_props = []
    resolve_schema_issues(
        sub_obj_namespace, isi_schema, required_props, is_response_object)

    for prop_name, prop in list(isi_schema['properties'].items()):
        if 'type' not in prop:
            if 'enum' in prop:
                log.warning(('Invalid enum prop with no type in object %s '
                             'prop %s: %s'), isi_obj_name, prop_name, prop)
                prop['type'] = 'string'
            else:
                continue  # must be a $ref
        if 'required' in prop:
            if prop['required']:
                # Often the PAPI will have a required field whose value can be
                # either a real value, such as a string, or it can be a null,
                # which Swagger can not deal with. This is only problematic
                # in objects that are returned as a response because it ends up
                # causing the Swagger code to throw an exception upon receiving
                # a PAPI response that contains null values for the 'required'
                # fields. So if the type is a multi-type (i.e. list) and
                # is_response_object is True, then we don't add the field to
                # the list of required fields.
                if (not is_response_object or
                        (not isinstance(prop['type'], list) and
                         prop_name not in
                         NON_REQUIRED_PROPS.get(sub_obj_namespace, []))):
                    required_props.append(prop_name)
                if prop_name in NON_REQUIRED_PROPS.get(sub_obj_namespace, []):
                    log.warning("Required property '%s' may be null", prop_name)
            del prop['required']
        if isinstance(prop['type'], list):
            # swagger doesn't like lists for types
            # so use the first type that is not 'null'
            prop = isi_schema['properties'][prop_name] = \
                find_best_type_for_prop(prop)
            if 'required' in prop:
                del prop['required']

        if prop['type'] == 'object':
            sub_obj_name = prop_name.title().replace('_', '')
            # store the description in the ref for property object refs
            if 'description' in prop:
                prop_description = prop['description']
                del prop['description']
            else:
                prop_description = ''

            obj_ref = isi_schema_to_swagger_object(
                sub_obj_namespace, sub_obj_name, prop,
                class_ext_post_fix, is_response_object)
            isi_schema['properties'][prop_name] = {
                'description': prop_description, '$ref': obj_ref}

        elif (isinstance(prop['type'], dict) and
              prop['type']['type'] == 'object'):
            sub_obj_name = prop_name.title().replace('_', '')
            # store the description in the ref for property object refs
            if 'description' in prop:
                prop_description = prop['description']
                del prop['description']
            else:
                prop_description = ''

            obj_ref = isi_schema_to_swagger_object(
                sub_obj_namespace, sub_obj_name, prop['type'],
                class_ext_post_fix, is_response_object)
            isi_schema['properties'][prop_name] = {
                'description': prop_description, '$ref': obj_ref}
        elif prop['type'] == 'array':
            isi_to_swagger_array_prop(
                prop, prop_name, isi_obj_name,
                isi_obj_name_space, isi_schema['properties'],
                class_ext_post_fix, is_response_object)
        # code below is work around for bug in /auth/access/<USER> end point
        elif prop['type'] == 'string' and 'enum' in prop:
            new_enum = []
            for item in prop['enum']:
                if item is None:
                    continue
                if not isinstance(item, str) and not isinstance(item, unicode):
                    log.warning(('Invalid prop with multi-type '
                                 'enum in object %s prop %s: %s'),
                                isi_obj_name, prop_name, prop)
                    # Swagger can't deal with multi-type enums so just
                    # eliminate the enum.
                    new_enum = []
                    break
                # Swagger doesn't know how to interpret '@DEFAULT' values
                elif len(item) > 0 and item[0] != '@':
                    new_enum.append(item)
            if new_enum:
                prop['enum'] = new_enum
            else:
                del prop['enum']
        elif prop['type'] == 'any':
            # Swagger does not support 'any'
            prop['type'] = 'string'
        elif prop['type'] == 'int':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['type'] = 'integer'
        elif prop['type'] == 'bool':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['type'] = 'boolean'
        elif prop['type'] == 'time':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['type'] = 'integer'
        elif prop['type'] == 'integer 0 - 10':
            log.warning('Invalid prop type in object %s prop %s: %s',
                        isi_obj_name, prop_name, prop)
            prop['type'] = 'integer'
            prop['minimum'] = 0
            prop['maximum'] = 10
        elif prop['type'] == 'integer':
            if 'maximum' in prop and prop['maximum'] > MAX_INTEGER_SIZE:
                prop['maximum'] = MAX_INTEGER_SIZE

        if prop['type'] == 'string':
            if 'maxLength' in prop and prop['maxLength'] > MAX_STRING_SIZE:
                prop['maxLength'] = MAX_STRING_SIZE

            # the custom added keyword 'x-sensitive' is custom, not
            # recognized by swagger, and thus needs to be removed
            # this keyword will only exist where prop type is a string
            if X_SENSITIVE in prop:
                del prop[X_SENSITIVE]

        if 'pattern' in prop:
            if prop_name == 'subsystem':
                prop['pattern'] = \
                    codecs.unicode_escape_encode(codecs
                                                 .unicode_escape_decode(
                        prop['pattern'])[0])[0]

    if required_props:
        isi_schema['required'] = required_props
    elif 'required' in isi_schema:
        # required field in top-level object is redundant
        del isi_schema['required']

    return find_or_add_obj_def(
        isi_schema, sub_obj_namespace, class_ext_post_fix)


def get_object_def(obj_name):
    """Lookup object definition."""
    cur_obj = SWAGGER_DEFS[obj_name]
    if 'allOf' in cur_obj:
        ref_obj_name = os.path.basename(cur_obj['allOf'][0]['$ref'])
        ref_obj = get_object_def(ref_obj_name)

        full_obj_def = {}
        full_obj_def['properties'] = cur_obj['allOf'][-1]['properties'].copy()
        full_obj_def['properties'].update(ref_obj['properties'])
        if 'required' in cur_obj['allOf'][-1]:
            full_obj_def['required'] = list(cur_obj['allOf'][-1]['required'])
        if 'required' in ref_obj:
            try:
                full_obj_def['required'].extend(ref_obj['required'])
                # eliminate dups
                full_obj_def['required'] = list(set(full_obj_def['required']))
            except KeyError:
                full_obj_def['required'] = list(ref_obj['required'])
        return full_obj_def
    return cur_obj


def find_or_add_obj_def(new_obj_def, new_obj_name,
                        class_ext_post_fix):
    """Reuse existing object def if there's a match or add a new one.

    Return the 'definitions' path.
    """
    extended_obj_name = new_obj_name
    for obj_name in SWAGGER_DEFS:
        existing_obj_def = get_object_def(obj_name)
        if new_obj_def['properties'] == existing_obj_def['properties']:
            if sorted(new_obj_def.get('required', [])) == \
                    sorted(existing_obj_def.get('required', [])):
                return '#/definitions/' + obj_name
            else:
                # the only difference is the list of required props, so use
                # the existing_obj_def as the basis for an extended object.
                extended_obj_name = obj_name
                break

    if extended_obj_name in SWAGGER_DEFS:
        # TODO at this point the subclass mechanism depends on the data models
        # being generated in the correct order, where base classes are
        # generated before sub classes. This is done by processing the
        # endpoints in order: POST base endpoint, all item endpoints, GET base
        # endpoint. This seems to work for nfs exports, obviously won't work if
        # the same pattern that nfs exports uses is not repeated by the other
        # endpoints.
        # crude/limited subclass generation
        existing_obj = get_object_def(extended_obj_name)
        is_extension = True
        existing_props = existing_obj['properties']
        existing_required = existing_obj.get('required', [])

        for prop_name, prop in list(existing_props.items()):
            if prop_name not in new_obj_def['properties']:
                is_extension = False
                break
            elif new_obj_def['properties'][prop_name] != prop:
                is_extension = False
                break
            elif (prop_name in existing_required and
                  prop_name not in new_obj_def.get('required', [])):
                is_extension = False
                break
        if is_extension:
            extended_obj_def = {
                'allOf': [{'$ref': '#/definitions/' + extended_obj_name}]
            }
            unique_props = {}
            unique_required = new_obj_def.get('required', [])
            for prop_name in new_obj_def['properties']:
                if prop_name in existing_required:
                    unique_required.remove(prop_name)
                # delete properties that are shared and not required
                if prop_name not in existing_props or (
                        prop_name in existing_props and
                        prop_name in unique_required):
                    unique_props[prop_name] = \
                        new_obj_def['properties'][prop_name]
            new_obj_def['properties'] = unique_props
            extended_obj_def['allOf'].append(new_obj_def)
        else:
            extended_obj_def = new_obj_def

        while new_obj_name in SWAGGER_DEFS:
            new_obj_name += class_ext_post_fix
        SWAGGER_DEFS[new_obj_name] = extended_obj_def
    else:
        SWAGGER_DEFS[new_obj_name] = new_obj_def
    return '#/definitions/' + new_obj_name


def check_swagger_op_is_unique(api_name, obj_namespace, obj_name, end_point):
    """Ensure Swagger operation is unique."""
    op_id = '{}:{}:{}'.format(api_name, obj_namespace, obj_name)
    if op_id in GENERATED_OPS:
        raise RuntimeError(
            'Found duplicate operation {} for end points:\n{}\n{}'.format(
                op_id, GENERATED_OPS[op_id], end_point))
    GENERATED_OPS[op_id] = end_point


def build_swagger_name(names, start, end, omit_params=False):
    """Build Swagger name."""
    swagger_name = ''
    for index in range(start, end):
        name = names[index]
        next_name = re.sub('[^0-9a-zA-Z]+', '', name.title())
        if name.startswith('<') and name.endswith('>') and omit_params is True:
            continue  # API names dont use Param fields - it's redundant
        # If there is an 'ID' in th middle of the URL then try to replace
        # with a better name using the names from the URL that come before.
        # Special case for 'LNN' which stands for Logical Node Number.
        if name.endswith('ID>') or name == '<LNN>':
            next_name = 'Item'  # default name if we can't find a better name
            for sub_index in reversed(list(range(index))):
                prev_name = re.sub(
                    '[^0-9a-zA-Z]+', '', names[sub_index].title())
                post_fix_used = PostFixUsed()
                prev_name_single = plural_obj_name_to_singular(
                    prev_name, post_fix_used=post_fix_used)
                # if post_fix_used is true then the prev_name is not capable of
                # being singularized (probably because it is already singular).
                if post_fix_used.flag is False:
                    next_name = prev_name_single
                    break
        swagger_name += next_name
    return swagger_name


def build_isi_api_name(names):
    """Build isi API name."""
    start_index = 0
    end_index = 1
    # use the first item or the last instance of <FOO> that is not on the end
    # point URL.
    for index in reversed(list(range(len(names) - 1))):
        name = names[index]
        if name.startswith('<') and name.endswith('>'):
            end_index = index - 1 if index > 2 else index
            break
    isi_api_name = build_swagger_name(
        names, start_index, end_index, omit_params=True)
    # return the name and the end index so the IsiObjNameSpace and IsiObjName
    # can be built starting from there.
    return isi_api_name, end_index


def end_point_path_to_api_obj_name(end_point):
    """Convert the end point url to an object and api name."""
    if end_point[0] == '/':
        end_point = end_point[1:]
    names = end_point.split('/')
    # discard the version
    del names[0]
    # deal with special cases of very short end point URLs
    if len(names) == 2:
        isi_api_name = re.sub('[^0-9a-zA-Z]+', '', names[0].title())
        isi_obj_name_space = isi_api_name
        isi_obj_name = re.sub('[^0-9a-zA-Z]+', '', names[1].title())
        return isi_api_name, isi_obj_name_space, isi_obj_name
    elif len(names) == 1:
        isi_api_name = re.sub('[^0-9a-zA-Z]+', '', names[0].title())
        isi_obj_name_space = ''
        isi_obj_name = isi_api_name
        return isi_api_name, isi_obj_name_space, isi_obj_name

    isi_api_name, next_index = build_isi_api_name(names)
    if next_index == len(names) - 1:
        isi_obj_name_space = ''
        isi_obj_name = build_swagger_name(names, next_index, len(names))
    else:
        isi_obj_name_space = build_swagger_name(
            names, next_index, next_index + 1)
        isi_obj_name = build_swagger_name(names, next_index + 1, len(names))

    return isi_api_name, isi_obj_name_space, isi_obj_name


def to_swagger_end_point(end_point_path):
    """Convert to Swagger end point path."""
    new_end_point_path = '/'
    for partial_path in end_point_path.split('/'):
        input_param = partial_path.replace('<', '{').replace('>', '}')
        if input_param != partial_path:
            partial_path = input_param.title()
        new_end_point_path = os.path.join(new_end_point_path, partial_path)
    return new_end_point_path


def create_swagger_operation(isi_api_name, isi_obj_name_space, isi_obj_name,
                             operation, isi_input_args, isi_input_schema,
                             isi_resp_schema, input_schema_param_obj_name=None,
                             class_ext_post_fix='Extended'):
    """Create Swagger operation object."""
    swagger_operation = {}
    swagger_operation['tags'] = [isi_api_name]
    swagger_operation['description'] = isi_input_args['description']
    if 'properties' in isi_input_args:
        # PAPI only uses url query params
        swagger_param_type = 'query'
        swagger_params = isi_props_to_swagger_params(
            isi_input_args['properties'], swagger_param_type)
    else:
        swagger_params = []

    swagger_operation['operationId'] = \
        operation + isi_obj_name_space + isi_obj_name

    if isi_input_schema is not None:
        # sometimes the url parameter gets same name, so the
        # input_schema_param_obj_name variable is used to prevent that
        if input_schema_param_obj_name is None:
            input_schema_param_obj_name = isi_obj_name
        obj_ref = isi_schema_to_swagger_object(
            isi_obj_name_space, input_schema_param_obj_name,
            isi_input_schema, class_ext_post_fix)
        input_schema_param = {}
        input_schema_param['in'] = 'body'
        input_schema_param['name'] = \
            isi_obj_name_space + input_schema_param_obj_name
        input_schema_param['required'] = True
        input_schema_param['schema'] = {'$ref': obj_ref}
        swagger_params.append(input_schema_param)
        # just use the operation for the response because it seems like
        # all the responses to POST have the same schema
        isi_resp_obj_name_space = \
            operation[0].upper() + operation[1:] + isi_obj_name_space
        isi_resp_obj_name = isi_obj_name + 'Response'
    else:
        isi_resp_obj_name_space = isi_obj_name_space
        isi_resp_obj_name = isi_obj_name

    swagger_operation['parameters'] = swagger_params

    # OneFS 8.1.x response schemas are a multi-type array
    if isi_resp_schema is not None and 'type' in isi_resp_schema:
        if (isinstance(isi_resp_schema['type'], list) and
                isinstance(isi_resp_schema['type'][0], dict) and
                'description' in isi_resp_schema['type'][0] and
                isi_resp_schema['type'][0]['description'] == \
                "A list of errors that may be returned."):
            # pop the errors response object off the list
            isi_resp_schema = isi_resp_schema['type'][1]

    # create responses
    swagger_responses = {}
    if isi_resp_schema is not None:
        try:
            response_type = isi_resp_schema['type']
        except KeyError:
            # There is some code in isi_schema_to_swagger_object that
            # handles response schemas that don't have a 'type' so just force
            # type to be an 'object' so that isi_schema_to_swagger_object
            # can fix.
            response_type = 'object'

        # create 200 response
        swagger_200_resp = {}
        # the 'type' of /4/protocols/smb/shares and /3/antivirus/servers is a
        # list of objects, so treat them the same as 'type' == 'object'
        if response_type == 'object' or isinstance(response_type, list):
            obj_ref = isi_schema_to_swagger_object(
                isi_resp_obj_name_space, isi_resp_obj_name, isi_resp_schema,
                class_ext_post_fix, is_response_object=True)
            swagger_200_resp['description'] = isi_input_args['description']
            swagger_200_resp['schema'] = {'$ref': obj_ref}
        else:
            # the 'type' of /2/cluster/external-ips is array
            swagger_200_resp['description'] = isi_resp_schema['description']
            swagger_200_resp['schema'] = {'type': response_type}
            if response_type == 'array':
                isi_to_swagger_array_prop(
                    isi_resp_schema,
                    'items', isi_resp_obj_name, isi_resp_obj_name_space,
                    isi_resp_schema, class_ext_post_fix,
                    is_response_object=True)
                swagger_200_resp['schema']['items'] = isi_resp_schema['items']
        # add to responses
        swagger_responses['200'] = swagger_200_resp
    else:
        # if no response schema then default response is 204
        swagger_204_resp = {}
        swagger_204_resp['description'] = 'Success.'
        swagger_responses['204'] = swagger_204_resp
    # create default 'error' response
    swagger_error_resp = {}
    swagger_error_resp['description'] = 'Unexpected error'
    swagger_error_resp['schema'] = {'$ref': '#/definitions/Error'}
    # add to responses
    swagger_responses['default'] = swagger_error_resp
    # add responses to the operation
    swagger_operation['responses'] = swagger_responses

    return swagger_operation


def add_path_params(swagger_params, extra_path_params):
    """Add Swagger path parameters."""
    for param_name, param_type in extra_path_params:
        path_param = build_path_param(param_name, param_type)
        swagger_params.append(path_param)


def build_path_param(param_name, param_type):
    """Build path parameter."""
    path_param = {}
    path_param['name'] = param_name
    path_param['in'] = 'path'
    path_param['required'] = True
    path_param['type'] = param_type
    if param_name in URL_ENCODE_PARAMS:
        # Isilon extension to Swagger for URL encoding
        path_param[X_ISI_URL_ENCODE_PATH_PARAM] = True
    return path_param


def isi_post_to_swagger_path(isi_api_name, isi_obj_name_space, isi_obj_name,
                             isi_desc_json, isi_path_params):
    """Convert isi POST base endpoint description to Swagger path."""
    swagger_path = {}
    isi_post_args = isi_desc_json['POST_args']
    one_obj_name = plural_obj_name_to_singular(isi_obj_name, post_fix='Item')

    post_input_schema = isi_desc_json.get('POST_input_schema', None)
    post_resp_schema = isi_desc_json.get('POST_output_schema', None)

    # Avoid duplicate operationId between /1/auth/mapping/identities
    # and /1/auth/mapping/identities/<SOURCE> for POST method
    if isi_obj_name_space + one_obj_name == 'MappingIdentity':
        one_obj_name = isi_obj_name

    operation = 'create'
    swagger_path['post'] = create_swagger_operation(
        isi_api_name, isi_obj_name_space, one_obj_name, operation,
        isi_post_args, post_input_schema, post_resp_schema,
        None, 'CreateParams')
    add_path_params(swagger_path['post']['parameters'], isi_path_params)

    return swagger_path


def isi_put_to_swagger_path(isi_api_name, isi_obj_name_space, isi_obj_name,
                            isi_desc_json, isi_path_params):
    """Convert isi PUT base endpoint description to Swagger path."""
    swagger_path = {}
    input_args = isi_desc_json['PUT_args']

    input_schema = isi_desc_json['PUT_input_schema']
    operation = 'update'
    swagger_path['put'] = create_swagger_operation(
        isi_api_name, isi_obj_name_space, isi_obj_name, operation,
        input_args, input_schema, None)
    add_path_params(swagger_path['put']['parameters'], isi_path_params)

    return swagger_path


def isi_delete_to_swagger_path(isi_api_name, isi_obj_name_space, isi_obj_name,
                               isi_desc_json, isi_path_params):
    """Convert isi DELETE base endpoint description to Swagger path."""
    swagger_path = {}
    input_args = isi_desc_json['DELETE_args']
    operation = 'delete'
    swagger_path['delete'] = create_swagger_operation(
        isi_api_name, isi_obj_name_space, isi_obj_name, operation,
        input_args, None, None)
    add_path_params(swagger_path['delete']['parameters'], isi_path_params)

    return swagger_path


def isi_get_to_swagger_path(isi_api_name, isi_obj_name_space, isi_obj_name,
                            isi_desc_json, isi_path_params):
    """Convert isi GET base endpoint description to Swagger path."""
    swagger_path = {}
    isi_get_args = isi_desc_json['GET_args']
    get_resp_schema = isi_desc_json['GET_output_schema']
    if 'POST_args' in isi_desc_json:
        operation = 'list'
    else:
        # if no POST then this is a singleton so use 'get' for operation
        operation = 'get'
    swagger_path['get'] = create_swagger_operation(
        isi_api_name, isi_obj_name_space, isi_obj_name, operation,
        isi_get_args, None, get_resp_schema)
    add_path_params(swagger_path['get']['parameters'], isi_path_params)

    return swagger_path


def isi_item_to_swagger_path(isi_api_name, isi_obj_name_space, isi_obj_name,
                             isi_desc_json, single_obj_post_fix,
                             item_input_type, extra_path_params):
    """Convert isi item endpoint description to Swagger path."""
    swagger_path = {}
    # first deal with POST and PUT in order to create the objects that are
    # used in the GET
    post_fix_used = PostFixUsed()
    one_obj_name = plural_obj_name_to_singular(
        isi_obj_name, post_fix=single_obj_post_fix,
        post_fix_used=post_fix_used)
    # if the single_obj_post_fix was not used to make it singular then add 'Id'
    # to item_id param name
    if post_fix_used.flag is False:
        item_id = isi_obj_name_space + one_obj_name + 'Id'
        # use default name of isi_obj_name_space + one_obj_name
        input_schema_param_obj_name = None
    else:
        item_id = isi_obj_name_space + one_obj_name
        input_schema_param_obj_name = one_obj_name + 'Params'
    item_id_url = '/{' + item_id + '}'
    item_id_param = build_path_param(item_id, item_input_type)

    if 'PUT_args' in isi_desc_json:
        isi_put_args = isi_desc_json['PUT_args']
        if 'PUT_input_schema' in isi_desc_json:
            item_input_schema = isi_desc_json['PUT_input_schema']
        else:
            item_input_schema = None
        operation = 'update'
        swagger_path['put'] = create_swagger_operation(
            isi_api_name, isi_obj_name_space, one_obj_name, operation,
            isi_put_args, item_input_schema, None,
            input_schema_param_obj_name)
        # hack to get operation to insert ById to make the op name make sense
        if one_obj_name[-2:] == 'Id':
            swagger_path['put']['operationId'] = \
                operation + isi_obj_name_space + one_obj_name[:-2] + 'ById'
        # add the item-id as a url path parameter
        put_id_param = item_id_param.copy()
        put_id_param['description'] = isi_put_args['description']
        swagger_path['put']['parameters'].append(put_id_param)
        add_path_params(swagger_path['put']['parameters'], extra_path_params)

    if 'DELETE_args' in isi_desc_json:
        isi_delete_args = isi_desc_json['DELETE_args']
        operation = 'delete'
        swagger_path['delete'] = create_swagger_operation(
            isi_api_name, isi_obj_name_space, one_obj_name, operation,
            isi_delete_args, None, None)
        # hack to get operation to insert ById to make the op name make sense
        if one_obj_name[-2:] == 'Id':
            swagger_path[operation]['operationId'] = \
                operation + isi_obj_name_space + one_obj_name[:-2] + 'ById'
        # add the item-id as a url path parameter
        del_id_param = item_id_param.copy()
        del_id_param['description'] = isi_delete_args['description']
        swagger_path['delete']['parameters'].append(del_id_param)
        add_path_params(
            swagger_path['delete']['parameters'], extra_path_params)

    if 'GET_args' in isi_desc_json:
        isi_get_args = isi_desc_json['GET_args']
        get_resp_schema = isi_desc_json['GET_output_schema']
        operation = 'get'
        # use the plural name so that the GET base end point's response
        # becomes subclass of this response object schema model
        swagger_path['get'] = create_swagger_operation(
            isi_api_name, isi_obj_name_space, isi_obj_name, operation,
            isi_get_args, None, get_resp_schema)
        # hack to force the api function to be 'get<SingleObj>'
        swagger_path['get']['operationId'] = \
            operation + isi_obj_name_space + one_obj_name
        # hack to get operation to insert ById to make the op name make sense
        if one_obj_name[-2:] == 'Id':
            swagger_path[operation]['operationId'] = \
                operation + isi_obj_name_space + one_obj_name[:-2] + 'ById'
        # add the item-id as a url path parameter
        get_id_param = item_id_param.copy()
        get_id_param['description'] = isi_get_args['description']
        swagger_path['get']['parameters'].append(get_id_param)
        add_path_params(swagger_path['get']['parameters'], extra_path_params)

    if 'POST_args' in isi_desc_json:
        isi_post_args = isi_desc_json['POST_args']
        post_input_schema = isi_desc_json['POST_input_schema']
        if 'POST_output_schema' in isi_desc_json:
            post_resp_schema = isi_desc_json['POST_output_schema']
        else:
            post_resp_schema = None
        operation = 'create'
        swagger_path['post'] = create_swagger_operation(
            isi_api_name, isi_obj_name_space, one_obj_name, operation,
            isi_post_args, post_input_schema, post_resp_schema,
            None, 'CreateParams')
        # hack to get operation to insert ById to make the op name make sense
        if one_obj_name[-2:] == 'Id':
            swagger_path['post']['operationId'] = \
                operation + isi_obj_name_space + one_obj_name[:-2] + 'ById'
        # Issue #11: add the item-id as a url path parameter
        post_id_param = item_id_param.copy()
        post_id_param['description'] = isi_post_args['description']
        swagger_path['post']['parameters'].append(post_id_param)

        add_path_params(swagger_path['post']['parameters'], extra_path_params)

    return item_id_url, swagger_path


def parse_path_params(end_point_path):
    """Parse path parameters."""
    numeric_item_types = ['Lnn', 'Zone', 'Port', 'Lin']
    params = []
    for partial_path in end_point_path.split('/'):
        if (not partial_path or partial_path[0] != '<' or
                partial_path[-1] != '>'):
            continue
        # remove all non alphanumeric characters
        param_name = re.sub('[^0-9a-zA-Z]+', '', partial_path.title())
        if param_name in numeric_item_types:
            param_type = 'integer'
        else:
            param_type = 'string'
        params.append((param_name, param_type))

    return params


def get_endpoint_paths(source_node_or_cluster, port, base_url, session,
                       exclude_end_points, cached_schemas):
    """
    Gets the full list of PAPI URIs reported by source_node_or_cluster using
    the ?describe&list&json query arguments at the root level.
    Returns the URIs as a list of tuples where collection resources appear as
    (<collection-uri>, <single-item-uri>) and non-collection/static resources
    appear as (<uri>,None).
    """
    if 'directory' not in cached_schemas:
        desc_list_parms = {'describe': '', 'json': '', 'list': ''}
        url = 'https://' + source_node_or_cluster + ':' + port + base_url
        resp = requests_with_session(
            session, url, params=desc_list_parms)
        end_point_list_json = resp['directory']
        cached_schemas['directory'] = end_point_list_json
    else:
        end_point_list_json = cached_schemas['directory']
    # calls get_endpoint_paths from common_resources
    return common_resources.get_endpoint_paths(end_point_list_json, exclude_end_points)


def resolve_schema_issues(definition_name, isi_schema,
                          required_props, is_response_object):
    """Correct invalid PAPI schemas."""
    props = isi_schema['properties']
    # issue pf - 117082 [list_sync_jobs throwing exception when SyncIQ jobs other than copy or sync are present]
    if definition_name.startswith('SyncJobs'):
        if props['jobs']['items']['properties']['policy']['properties']['action']['enum'] == ['copy', 'sync']:
            props['jobs']['items']['properties']['policy']['properties']['action']['enum'] = ["none", "copy", "move",
                                                                                              "remove", "sync",
                                                                                              "allow_write",
                                                                                              "allow_write_revert",
                                                                                              "resync_prep",
                                                                                              "resync_prep_domain_mark",
                                                                                              "resync_prep_restore",
                                                                                              "resync_prep_finalize",
                                                                                              "resync_prep_commit",
                                                                                              "snap_revert_domain_mark",
                                                                                              "synciq_domain_mark",
                                                                                              "worm_domain_mark"]
    # Issue #12: Correct misspellings
    if definition_name == 'DebugStatsUnknown':
        if 'descriprion' in isi_schema:
            isi_schema['description'] = isi_schema['descriprion']
            del isi_schema['descriprion']
            log.warning("Found 'description' misspelled as 'descriprion'")
    # Issue #13: Correct properties schema
    elif definition_name == 'StatisticsOperation':
        if 'operations' in props:
            operations = props['operations'][0]['operation']
            if operations['required']:
                isi_schema['required'] = True
            props['operation'] = operations
            del props['operations']
            log.warning("Replace 'operations' property with 'operation'")
    elif (definition_name.startswith('StoragepoolNodepool') or
          definition_name.startswith('StoragepoolStoragepool')):
        if 'health_flags' in isi_schema:
            props['health_flags'] = isi_schema['health_flags']
            del isi_schema['health_flags']
            log.warning("Move 'health_flags' property under 'properties'")
    elif definition_name == 'EventEventgroupOccurrences':
        if 'eventgroup-occurrences' in props:
            props['eventgroups'] = props['eventgroup-occurrences']
            del props['eventgroup-occurrences']
            log.warning("Found 'eventgroups' as 'eventgroup-occurrences'")
    # Issue #22: Correct naming of interface as interfaces
    elif (definition_name == 'NetworkInterfaces' or
          definition_name == 'PoolsPoolInterfaces'):
        if 'interface' in props:
            props['interfaces'] = props['interface']
            del props['interface']
            log.warning("Found 'interfaces' misspelled as 'interface'")
    elif definition_name == 'HardeningStatusStatus':
        if 'status_text' in props:
            props['message'] = props['status_text']
            del props['status_text']
            log.warning("Found 'message' labeled as 'status_text'")
    elif definition_name == 'NdmpLogsNode':
        if 'logs:' in props:
            props['logs'] = props['logs:']
            del props['logs:']
            log.warning("Found 'logs' misspelled as 'logs:'")
    elif definition_name == 'StatisticsHistoryStat':
        if 'resolution' not in props:
            props['resolution'] = {'type': 'integer'}
            log.warning("Added missing 'resolution' property")
    elif definition_name == 'EventCategory':
        if 'category_name' in props and 'category_description' in props:
            props['id_name'] = props['category_name']
            del props['category_name']
            props['name'] = props['category_description']
            del props['category_description']
            props['id']['type'] = 'string'
            log.warning("Found event category properties mislabeled")
    elif definition_name.startswith('EventEventlist'):
        if 'eventlist' in props:
            props['eventlists'] = props['eventlist']
            del props['eventlist']
            log.warning("Found 'eventlists' mislabeled as 'eventlist'")
        if 'event_id' in props:
            props['event'] = props['event_id']
            del props['event_id']
            log.warning("Found 'event' mislabeled as 'event_id'")
        if (definition_name == 'EventEventlistsEventlistItemEvent' or
                definition_name == 'EventEventlistEvent'):
            if 'lnn' not in props and 'resolve_time' not in props:
                props['lnn'] = {'type': 'integer'}
                props['resolve_time'] = {'type': 'integer'}
                log.warning("Found 'lnn' and 'resolve_time' props missing")
    elif definition_name == 'EventChannels':
        if 'alert-conditions' in props:
            props['channels'] = props['alert-conditions']
            del props['alert-conditions']
            log.warning("Found 'channels' mislabeled as 'alert-conditions'")
    elif definition_name == 'EventSettings':
        if 'settings' not in props and 'maintenance' in props:
            isi_schema['properties'] = {'settings': isi_schema.copy()}
            log.warning("Found missing event 'settings' property")
    elif definition_name == 'SmbShares' and 'settings' in props:
        props['shares'] = {
            'items': props['settings'], 'minItems': 0, 'type': 'array'}
        del props['settings']
        log.warning("Found 'shares' mislabeled as 'settings'")
    elif (definition_name.startswith('SmbShares') or
          definition_name.startswith('NfsExports')):
        if 'resume' in props and 'total' in props and 'digest' not in props:
            props['digest'] = {'type': 'string'}
            log.warning("Found missing 'digest' property")
    elif definition_name == 'NfsCheck':
        if 'messages' in props:
            props['message'] = props['messages']
            del props['messages']
            log.warning("Found 'mesage' mislabeled as 'messages'")
    elif definition_name.startswith('SmbLogLevelFilters'):
        if 'resume' in props and 'total' in props:
            del props['resume']
            del props['total']
            log.warning("Removing invalid 'resume' and 'total' properties")
    elif definition_name == 'NdmpUsers':
        if 'id' in props and 'name' in props:
            props['users'] = {
                'items': {'properties': props.copy()},
                'type': 'array'
            }
            del props['id']
            del props['name']
            log.warning("Move NDMP user properties into an array")
    elif definition_name == 'SettingsMapping' and 'id' not in props:
        if 'domain' in props and 'mapping' in props and 'type' in props:
            props['id'] = {'type': 'string'}
            log.warning("Added missing 'id' property")
    elif definition_name == 'JobEvent' or definition_name == 'JobReport':
        if ('fmt_type' not in props and 'raw_type' not in props
                and 'value' in props):
            props['fmt_type'] = {'type': 'string'}
            props['raw_type'] = {'type': 'string'}
            log.warning("Added missing 'fmt_type' and 'raw_type' properties")
    elif definition_name == 'JobPolicies' and 'types' in props:
        props['policies'] = props['types']
        del props['types']
        log.warning("Renamed 'types' property to 'policies'")

    for prop_name, prop in list(props.items()):

        # Issue #8: Remove invalid placement of required field
        if (definition_name == 'StoragepoolStatusUnhealthyItem' and
                prop_name == 'health_flags'):
            if 'required' in prop['items']:
                del prop['items']['required']
                log.warning("Remove 'required' from array items")
        # Issue #9: Remove duplicate `delete_child`
        elif ((definition_name == (
                'SmbSettingsGlobalSettingsAuditGlobalSaclItem')
               or definition_name == 'SmbSettingsGlobalAuditGlobalSaclItem')
              and prop_name == 'permission'):
            if 'items' in prop and 'enum' in prop['items']:
                prop['items']['enum'] = (
                    list(OrderedDict.fromkeys(prop['items']['enum'])))
                log.warning("Remove duplicate 'delete_child' from enum")
        # Issue #10: Remove invalid required field
        elif (definition_name.startswith('Job') and 'items' in prop and
              'required' in prop['items']):
            del prop['items']['required']
            log.warning("Remove invalid 'required' field")
        # Issue #12: Correct misspellings
        elif definition_name == 'AuthAccessAccessItem' and prop_name == 'id':
            if 'descriptoin' in prop:
                prop['description'] = prop['descriptoin']
                del prop['descriptoin']
                log.warning("Found 'description' misspelled as 'descriptoin'")
        elif definition_name.startswith('DebugStats'):
            if 'descriprion' in prop:
                prop['description'] = prop['descriprion']
                del prop['descriprion']
                log.warning("Found 'description' misspelled as 'descriprion'")
        elif definition_name.startswith('HealthcheckEvaluation'):
            if prop_name == 'run_status' and 'desciption' in prop:
                prop['description'] = prop['desciption']
                del prop['desciption']
                log.warning("Found 'description' misspelled as 'desciption'")
            if prop_name == 'delivery' and 'description:' in prop:
                prop['description'] = prop['description:']
                del prop['description:']
                log.warning("Found 'description' misspelled as 'description:'")
        elif definition_name.endswith('HealthcheckChecklist'):
            if prop_name == 'delivery' and 'description:' in prop:
                prop['description'] = prop['description:']
                del prop['description:']
                log.warning("Found 'description' misspelled as 'description:'")
        elif 'Subnet' in definition_name:
            if prop_name == 'sc_service_name' and 'description:' in prop:
                prop['description'] = prop['description:']
                del prop['description:']
                log.warning("Found 'description' misspelled as 'description:'")
        # Issue #14: Include hardware `devices` fields
        elif definition_name == 'HardwareTapes' and prop_name == 'devices':
            if 'media_changers' in prop and 'tapes' in prop:
                prop['type'] = 'object'
                prop['description'] = 'Information of Tape/MC device'
                prop['properties'] = {
                    'media_changers': {'items': prop['media_changers']},
                    'tapes': {'items': prop['tapes']}
                }
                del prop['media_changers']
                del prop['tapes']
                log.warning(("Move 'media_changers' and 'tapes' in 'devices'"
                             "property to nested 'properties' object"))
        # Issue #15: Correct nested array schema
        elif definition_name == 'EventEventgroupOccurrencesEventgroup':
            if prop_name == 'causes' and 'items' not in prop['items']:
                prop['items'] = prop['items']['type']
                prop['type'] = 'array'
                log.warning("Correct nested array schema in 'causes' property")
        # Remove custom `ignore_case` field
        elif definition_name.startswith('EventAlertCondition'):
            if 'ignore_case' in prop:
                del prop['ignore_case']
            if 'items' in prop and 'ignore_case' in prop['items']:
                del prop['items']['ignore_case']
            log.warning("Remove custom 'ignore_case' field")
        elif definition_name == 'HistogramStatByBreakout':
            if prop_name == 'data' and prop['type'] == 'array':
                if 'properties' in prop:
                    del prop['properties']
                    prop['items'] = {
                        'type': 'array',
                        'items': {'type': 'integer'}
                    }
                    log.warning("Correct 'data' properties array object")
        elif definition_name.startswith('Ndmp'):
            if prop['type'] == 'array' and 'properties' in prop:
                prop['items'] = {
                    'type': 'object',
                    'properties': prop['properties']
                }
                del prop['properties']
                log.warning("Move 'properties' into the 'items' object")
        elif definition_name.startswith('SummaryProtocolStatsProtocol'):
            if 'type' not in prop:
                prop['properties'] = prop.copy()
                for key in prop.keys():
                    if key not in ['properties']:
                        del prop[key]
                prop['type'] = 'object'
                log.warning("Move properties into the 'properties' object")
            elif prop_name == 'protocol' and prop['type'] == 'array':
                prop['type'] = 'object'
                prop['properties'] = {
                    'name': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': prop['data'][0]
                        }
                    }
                }
                del prop['data']
                log.warning("Restructure the 'protocol' property object")
        elif definition_name == 'SummaryProtocolStats':
            if prop_name == 'protocol-stats' and 'items' in prop:
                prop['type'] = prop['items']['type']
                prop['properties'] = prop['items']['properties']
                del prop['items']
                log.warning("'protocol-stats' is an object, not an array")
        elif definition_name == 'HardwareFcportsNode':
            if (prop_name == 'fcports' and prop['type'] == 'array' and
                    'properties' in prop):
                prop['items'] = prop['properties']
                del prop['properties']
                log.warning("Move 'fcports' array properties into 'items'")
        # Issue #22: Remove invalid status enum
        elif (definition_name == 'NetworkInterface' or
              definition_name == 'PoolsPoolInterfacesInterface'):
            if prop_name == 'status' and 'enum' in prop:
                del prop['enum']
                log.warning("Remove invalid 'status' enum")
        elif (definition_name == 'NetworkDnscache' or
              definition_name == 'NetworkExternal'):
            if prop_name == 'settings' and 'items' in prop:
                prop['type'] = prop['items']['type']
                prop['properties'] = prop['items']['properties']
                del prop['items']
                log.warning("Property 'settings' is an object, not an array")
        elif definition_name == 'HardeningStateState':
            if prop_name == 'state' and 'Other' not in prop['enum']:
                prop['enum'].append('Other')
                log.warning("Hardening state missing 'Other' in enum")
        elif definition_name.startswith('EventChannel'):
            if prop_name == 'type' and 'heartbeat' not in prop['enum']:
                prop['enum'].append('heartbeat')
                log.warning("Include missing 'heartbeat' in enum")
        elif definition_name == 'SmbLogLevelFiltersFilter':
            if prop_name == 'level' and 'enum' in prop:
                del prop['enum']
                log.warning("Removing enum with duplicate values")
        elif 'FileMatchingPattern' in definition_name:
            if prop_name == 'operator' and 'enum' in prop:
                del prop['enum']
                log.warning("Removing enum with special characters")
        elif definition_name.startswith('SnmpSettings'):
            if prop_name == 'system_contact' and 'pattern' in prop:
                prop['pattern'] = prop['pattern'].replace('{2,4}', '{2,7}')
                log.warning("Modified restrictive regex pattern")
        elif (definition_name.startswith('NodeDriveconfig') or
              definition_name.startswith('ClusterNodeDrive')):
            if 'default' in prop and prop['default'] == 'true':
                prop['default'] = True
                log.warning("Default 'true' value is a string, not a boolean")
            if 'default' in prop and prop['default'] == '30':
                prop['default'] = 30
                log.warning("Default '30' value is a string, not a integer")
        # protect against array out of bounds exception
        # elif definition_name.startswith('UpgradeClusterCommittedFeatures'):
        #    if 'bits' in prop_name:
        #        del prop['maxItems']
        # Swagger-parser complains about 'Infinity', replace with max float value
        if (definition_name.find('QuotaQuota') != -1):
            if prop_name == 'efficiency_ratio':
                props['efficiency_ratio']['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}".format(definition_name))
            elif prop_name == 'reduction_ratio':
                props['reduction_ratio']['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}".format(definition_name))
        if (definition_name.find('PerformanceSettings') != -1):
            if ((prop_name == 'target_protocol_read_latency_usec') or
                (prop_name == 'target_protocol_write_latency_usec')):
                props[prop_name]['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}, {}".format(definition_name, prop_name))
            elif prop_name == 'target_protocol_write_latency_usec':
                props['target_protocol_write_latency_usec']['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}".format(definition_name))
            elif prop_name == 'impact_multiplier':
                props["impact_multiplier"]["properties"]["impact_high"]['maximum'] = 1.79769e+308
                props["impact_multiplier"]["properties"]["impact_low"]['maximum'] = 1.79769e+308
                props["impact_multiplier"]["properties"]["impact_unset"]['maximum'] = 1.79769e+308
                props["impact_multiplier"]["properties"]["impact_medium"]['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}".format(definition_name))
        if (definition_name.find('PerformanceSettingsSettings') != -1):
            if ((prop_name == 'target_protocol_read_latency_usec') or
                (prop_name == 'target_protocol_write_latency_usec')):
                props[prop_name]['maximum'] = 1.79769e+308
                log.warning("Removing Infinity maximum: {}, {}".format(definition_name, prop_name))
        # Issue 67: Regex fail on supportassist settings on primary contact while getting 
        # details of Support Assist
        if definition_name.startswith('SupportassistSettings') or definition_name.startswith('ConnectivitySettings'):
            if prop_name == 'first_name' and 'pattern' in prop:
                prop['pattern'] = prop['pattern'].replace( "[\\p{L}\\p{M}*\\-\\.\\' ]*", "[a-zA-Z]*[\\-\\.\\']*")
                log.warning("Modified regex pattern")
            elif prop_name == 'last_name' and 'pattern' in prop:
                prop['pattern'] = prop['pattern'].replace("[\\p{L}\\p{M}*\\-\\.\\' ]*","[a-zA-Z]*[\\-\\.\\']*")
                log.warning("Modified regex pattern")
            elif prop_name == 'email':
                if 'default' in prop:
                    if prop['pattern'] == "^[a-zA-Z0-9._%-]+@([a-zA-Z0-9-]+\\.)+[a-zA-Z0-9]+$":
                        del prop['default']
                        log.warning("Deleted default value for email")
            elif prop_name == 'phone':
                if 'default' in prop:
                    if prop['pattern'] == "([\\.\\-\\+\\/\\sxX]*([0-9]+|[\\(\\d+\\)])+)+":
                        del prop['default']
                        log.warning("Deleted default value for phone")
            elif prop_name.__eq__("language"):
                    props["language"] = "En"
                    log.info("Modified language value")
        # Issue 35 : Getting changelist entries fails if physical or size of file is > 4GB
        if definition_name.startswith('ChangelistEntry'):
            if prop_name == 'physical_size' and 'maximum' in prop:
                del prop['maximum']
                log.warning("Deleted maximum value for physical_size")
            if prop_name == 'size' and 'maximum' in prop:
                del prop['maximum']
                log.warning("Deleted maximum value for size")
        # Modifing/removing invalid regex patterns
        if definition_name.startswith('EventChannel'):
            if prop_name == 'custom_template' and 'pattern' in prop:
                prop['pattern'] = prop["pattern"].replace("^((\\/[^\\/[:cntrl:]]+)(\\/?))*$", "^((\\/[^\\/]+)(\\/?))*$")
                log.warning("Modified regex pattern")
        if definition_name.startswith('Provider'):
            if prop_name == 'home_directory_template' and 'pattern' in prop:
                prop['pattern'] = prop["pattern"].replace("^((\\/[^\\/[:cntrl:]]+)(\\/?))*$", "^((\\/[^\\/]+)(\\/?))*$")
                log.warning("Modified regex pattern")
        if definition_name.startswith("SshSettings"):
            if prop_name == "subsystem" and "pattern" in prop:
                del prop["pattern"]
                log.warning("Removed regex pattern")
        # modify type from integer to object to as there is property 'date' in 'retention'
        if (definition_name.find('S3Objects') != -1):
            if prop_name == "retention":
                if "type" in prop and prop['type'] == "integer":
                    prop['type'] = "object"
                    if "properties" in prop and "date" in prop['properties']:
                        if "type" in prop['properties']['date'] and prop['properties']['date']['type'] == "uint64":
                            prop['properties']['date']['type'] = "number"
                            log.warning("modified unit64 type to number")
                    log.warning("Modified incorrect type number to object")
        # Fixing multiple types in 'switches' property from ClusterInventory
        if definition_name.startswith("ClusterInventory"):
            if prop_name == "switches":
                if "type" in prop and isinstance(prop['type'], list):
                    switch_list_type = prop['type'][0]
                    props[prop_name] = switch_list_type
                if "items" in props[prop_name] and "type" in props[prop_name]['items'] and isinstance(props[prop_name]['items']['type'], list):
                    item_type = props[prop_name]['items']['type'][0]
                    props[prop_name]['items'].pop('type')
                    props[prop_name]['items'].update(item_type)
def fix_multiple_data_types_in_schema(swagger_defs):
    for definition_name,definition_body in swagger_defs.items():
        if 'properties' in definition_body:
            for prop_name,prop in definition_body['properties'].items():

                if definition_name.startswith("HardeningReports") or definition_name.startswith("CreateHardeningApply"):
                    if prop_name =="current" or prop_name == "prescribed":
                        if "type" in prop and prop['type'] == "array":
                            prop['type'] = "object"
                            if "items" in prop:
                                del prop['items']
                            prop['description'] = "Specifies the current or prescribed hardening checklist or item, in the cluster timezone."
                            log.warning("Modified type to object to support multiple types")
                if definition_name.startswith('HealthcheckEvaluation'):
                    if prop_name == 'start_time':
                        if "type" in prop and prop["type"] == "number":
                            prop['type'] = "object"
                            prop.pop("minimum", None)
                            prop.pop("maximum", None)
                            prop['description'] = "Specifies the start time for a checklist or item, in the cluster timezone."
                            log.warning("Modified type to object to support multiple types")
                if definition_name.startswith("ClusterInventory"):
                    if prop_name == "member_id":
                        if "type" in prop and prop["type"] == "integer":
                            prop['type'] = "object"
                            prop.pop("minimum", None)
                            prop.pop("maximum", None)
                            prop['description'] = "Member ID."
                            log.warning("Modified type to object to support multiple types")
                    if prop_name == "reading_celsius":
                        if "type" in prop and prop["type"] == "integer":
                            prop['type'] = "object"
                            prop.pop("minimum", None)
                            prop.pop("maximum", None)
                            prop['description'] = "Temperature in Celsius."
                            log.warning("Modified type to object to support multiple types")                         
def main():
    """Main method for create_swagger_config executable."""

    argparser = argparse.ArgumentParser(
        description='Builds Swagger config from PAPI end point descriptions.')
    argparser.add_argument(
        '-i', '--input', dest='host',
        help='IP-address or hostname of OneFS cluster for input',
        action='store', default='localhost')
    argparser.add_argument(
        '-o', '--output', dest='output_file',
        help='Path to output OpenAPI specification', action='store')
    argparser.add_argument(
        '-u', '--username', dest='username',
        help='Username for cluster access',
        action='store', default=None)
    argparser.add_argument(
        '-p', '--password', dest='password',
        help='Password for cluster access',
        action='store', default=None)
    argparser.add_argument(
        '-d', '--defs', dest='defs_file',
        help='Path to file with pre-built OpenAPI definitions',
        action='store', default=None)
    argparser.add_argument(
        '-t', '--test', dest='test',
        help='Test mode on', action='store_true', default=False)
    argparser.add_argument(
        '-l', '--logging', dest='log_level',
        help='Logging verbosity level', action='store', default='INFO')
    argparser.add_argument(
        '-v', '--version', dest='onefs_version',
        help='OneFS version with 3 dots (e.g. 8.1.0.2)',
        action='store', default=None)
    argparser.add_argument(
        '-a', '--automation', dest='automation',
        help='Non interactive way of creating OAS from json.',
        action='store_true', default=False)
    args = argparser.parse_args()
    if args.automation:
        if (not(args.host and args.output_file)):
            print('\nPlease give appropriate arguments.'+'\n'+'Correct Usage : python3 create_swagger_config.py -i <cluster_ip> -o <output_file_path>'+' or python3 create_swagger_config.py -v <version> -o <output_filr_path>')
            exit()
        elif (not(args.onefs_version and args.output_file) and not args.host):
            print('\nPlease give appropriate arguments.'+'\n'+'Correct Usage : python3 create_swagger_config.py -i <cluster_ip> -o <output_file_path>'+' or python3 create_swagger_config.py -v <version> -o <output_filr_path>')
            exit()
    log.basicConfig(
        format='%(asctime)s %(levelname)s - %(message)s',
        datefmt='%I:%M:%S', level=getattr(log, args.log_level.upper()))

    if not args.onefs_version:
        if args.username is None:
            args.username = input(
                'Please provide username used for API access to {}: '.format(
                    args.host))
        if args.password is None:
            args.password = getpass.getpass('Password: ')

    swagger_json = {
        'swagger': '2.0',
        'host': 'YOUR_CLUSTER_HOSTNAME_OR_NODE_IP:8080',
        'info': {
            'version': '1',
            'title': 'Isilon SDK',
            'description': 'Isilon SDK - Language bindings for the OneFS API',
            'termsOfService': ('https://github.com/emccode/'
                               'emccode.github.io/wiki/EMC-CODE-Governance,'
                               '-Contributing,-and-Code-of-Conduct'),
            'contact': {
                'name': 'Isilon SDK Team',
                'email': 'sdk@isilon.com',
                'url': 'https://github.com/Isilon/isilon_sdk'
            },
            'license': {
                'name': 'MIT',
                'url': ('https://github.com/Isilon/'
                        'isilon_sdk/blob/master/LICENSE')
            }
        },
        'schemes': [
            'https'
        ],
        'consumes': [
            'application/json'
        ],
        'produces': [
            'application/json'
        ],
        'securityDefinitions': {
            'basicAuth': {
                'type': 'basic',
            }
        },
        'security': [{'basicAuth': []}],
        'paths': {},
        'definitions': {}
    }

    schemas_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'papi_schemas'))
    defs_file = os.path.join(schemas_dir, 'definitions.json')
    namespace_file = os.path.join(schemas_dir, 'namespace.json')

    if args.defs_file:
        defs_file = args.defs_file

    with open(defs_file, 'r') as def_file:
        SWAGGER_DEFS.update(json.loads(def_file.read()))
    with open(namespace_file, 'r') as namespace_paths:
        swagger_json['paths'] = json.loads(namespace_paths.read())

    swagger_json['definitions'] = SWAGGER_DEFS

    # Added session auth. So HTTPBasicAuth - not needed - auth variable replaced to {username, password} from arguments
    auth = {'username':args.username, 'pwd':args.password}
    base_url = '/platform'
    port = '8080'
    desc_parms = {'describe': '', 'json': ''}
    # Initialize session object and create session if onefs_version is not provided in argumnets
    session = None

    if not args.onefs_version:
        # Creation of session object for accessing APIs
        session = create_web_session(args.host, auth['username'],  auth['pwd']) 
        onefs_version = onefs_release_version(args.host, port, session)
    else:
        onefs_version = args.onefs_version

    cached_schemas = {}
    schemas_file = os.path.join(schemas_dir, '{}.json'.format(onefs_version))

    if args.onefs_version:
        with open(schemas_file, 'r') as schemas:
            cached_schemas = json.loads(schemas.read())
        papi_version = int(cached_schemas['version'])
    else:
        papi_version = int(onefs_papi_version(args.host, port, session))
        # invalid backport of handlers caused versioning break
        if papi_version == 5 and onefs_version[:5] == '8.0.1':
            papi_version = 4
        cached_schemas['version'] = papi_version
    swagger_json['info']['version'] = str(papi_version)

    # minLength and maxLength were not required before PAPI version 5
    if papi_version < 5:
        id_prop = SWAGGER_DEFS['CreateResponse']['properties']['id']
        del id_prop['maxLength']
        del id_prop['minLength']

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
        if base_end_point_path is None:
            tmp_base_endpoint_path = to_swagger_end_point(
                os.path.dirname(item_end_point_path))
            swagger_path = base_url + tmp_base_endpoint_path
            api_name, obj_namespace, obj_name = end_point_path_to_api_obj_name(
                tmp_base_endpoint_path)
        else:
            api_name, obj_namespace, obj_name = end_point_path_to_api_obj_name(
                base_end_point_path)
            swagger_path = base_url + to_swagger_end_point(base_end_point_path)

        check_swagger_op_is_unique(
            api_name, obj_namespace, obj_name, swagger_path)

        if item_end_point_path is not None:
            log.info('Processing %s', item_end_point_path)
            # next do the item PUT (i.e. update), DELETE, and GET because the
            # GET seems to be a limited version of the base path GET so the
            # subclassing works correct when done in this order

            if not args.onefs_version:
                url = 'https://{}:{}{}{}'.format(
                    args.host, port, base_url, item_end_point_path)
                resp = requests_with_session(
                    session, url, params=desc_parms)
                item_resp_json = resp
                if item_resp_json == None:
                    log.warning("Missing ?describe for API %s", item_end_point_path)
                    continue
                cached_schemas[item_end_point_path] = deepcopy(item_resp_json)

            else:
                item_resp_json = cached_schemas[item_end_point_path]

            singular_obj_postfix, item_input_type = parse_path_params(
                os.path.basename(item_end_point_path))[0]
            extra_path_params = parse_path_params(
                os.path.dirname(item_end_point_path))
            try:
                item_path_url, item_path = isi_item_to_swagger_path(
                    api_name, obj_namespace, obj_name, item_resp_json,
                    singular_obj_postfix, item_input_type,
                    extra_path_params)
                swagger_json['paths'][swagger_path + item_path_url] = item_path

                if 'HEAD_args' in item_resp_json:
                    log.warning('HEAD_args in: %s', item_end_point_path)

                success_count += 1
            except (KeyError, TypeError, RuntimeError) as err:
                log.error('Caught exception processing: %s',
                          item_end_point_path)
                log.error('%s: %s', type(err).__name__, err)
                if args.test:
                    traceback.print_exc(file=sys.stderr)
                fail_count += 1

        if base_end_point_path is not None:
            log.info('Processing %s', base_end_point_path)

            if not args.onefs_version:
                url = 'https://{}:{}{}{}'.format(
                    args.host, port, base_url, base_end_point_path)
                resp = requests_with_session(
                    session, url, params=desc_parms)
                base_resp_json = resp
                if base_resp_json == None:
                    log.warning('Missing ?describe for API %s', base_end_point_path)
                    continue
                cached_schemas[base_end_point_path] = deepcopy(base_resp_json)

            else:
                base_resp_json = cached_schemas[base_end_point_path]

            base_path_params = parse_path_params(base_end_point_path)
            base_path = {}
            # start with base path POST because it defines the base
            # creation object model
            try:
                if 'POST_args' in base_resp_json:
                    if base_end_point_path in MISSING_POST_RESPONSE:
                        base_resp_json['POST_output_schema'] = {}
                        log.warning("Removed invalid POST response schema")

                    base_path = isi_post_to_swagger_path(
                        api_name, obj_namespace, obj_name, base_resp_json,
                        base_path_params)

                if 'GET_args' in base_resp_json:
                    get_base_path = isi_get_to_swagger_path(
                        api_name, obj_namespace, obj_name, base_resp_json,
                        base_path_params)
                    base_path.update(get_base_path)

                if 'PUT_args' in base_resp_json:
                    put_base_path = isi_put_to_swagger_path(
                        api_name, obj_namespace, obj_name, base_resp_json,
                        base_path_params)
                    base_path.update(put_base_path)

                if 'DELETE_args' in base_resp_json:
                    del_base_path = isi_delete_to_swagger_path(
                        api_name, obj_namespace, obj_name, base_resp_json,
                        base_path_params)
                    base_path.update(del_base_path)

                if base_path:
                    swagger_json['paths'][swagger_path] = base_path

                if 'HEAD_args' in base_resp_json:
                    log.warning('HEAD_args in: %s', base_end_point_path)
                success_count += 1
            except (KeyError, TypeError, RuntimeError) as err:
                log.error('Caught exception processing: %s',
                          base_end_point_path)
                log.error('%s: %s', type(err).__name__, err)
                if args.test:
                    traceback.print_exc(file=sys.stderr)
                fail_count += 1

    log.info(('End points successfully processed: %s, failed to process: %s, '
              'excluded: %s.'),
             success_count, fail_count, len(exclude_end_points))
    if args.automation :
            if cached_schemas and not args.onefs_version:
               with open(schemas_file, 'w+') as schemas:
                   schemas.write(json.dumps(
                cached_schemas, sort_keys=True, indent=4,
                separators=(',', ': ')))
    else:
      if cached_schemas and not args.onefs_version and os.path.exists(os.getcwd()+'/papi_schemas/'+str(onefs_version)+'.json'):
        print('\nDo you want to overwrite existing schema - '+os.getcwd()+'/papi_schemas/'+str(onefs_version)+'.json'+' [Y/N] or [y/n] ')
        ch=input()[0]
        if(ch=='y' or ch=='Y'):
             with open(schemas_file, 'w+') as schemas:
                  schemas.write(json.dumps(
                cached_schemas, sort_keys=True, indent=4,
                separators=(',', ': ')))
        elif(ch=='n' or ch=='N'):
                print('\nPlease Enter the new file name : ')
                new_name=input()
                if new_name[-5:]!='.json' and new_name!=onefs_version:
                   new_name=new_name+'.json'
                   with open('papi_schemas/'+new_name, 'w+') as schemas:
                       schemas.write(json.dumps(
                cached_schemas, sort_keys=True, indent=4,
                separators=(',', ': ')))
                elif new_name == onefs_version or new_name==onefs_version+'.json': 
                    print('\nSchema file of this name alrady exists , Please restart the execution.')
                    exit()
                else :
                    print('\nInappropriate File name!!!!')
                    exit()
        else:
            print('\nInvalid input!!!')
            exit()
      elif cached_schemas and not args.onefs_version and (os.path.exists(os.getcwd()+'/papi_schemas/'+str(onefs_version)+'.json')==False):
         with open(schemas_file, 'w+') as schemas:
                  schemas.write(json.dumps(
                cached_schemas, sort_keys=True, indent=4,
                separators=(',', ': ')))
    class TMCSerializer(JSONEncoder):

          def default(self, value):

            if isinstance(value, bytes):
              return str(value)
            return super(TMCSerializer, self).default(value)

    fix_multiple_data_types_in_schema(swagger_defs = swagger_json['definitions'])

    if args.automation:
        with open(args.output_file, 'w') as output_file:
         output_file.write(json.dumps(
           swagger_json,cls=TMCSerializer, sort_keys=True, indent=4, separators=(',', ': ')))
    else:
     if(args.output_file is not None):
        with open(args.output_file, 'w') as output_file:
               output_file.write(json.dumps(
           swagger_json,cls=TMCSerializer, sort_keys=True, indent=4, separators=(',', ': ')))
     else :
        new_file=str(onefs_version)+'.json'
        if(os.path.exists(new_file)):
            print('\n Do you want to replace your existing OAS  : '+os.getcwd()+'/'+new_file +' Enter your choice :[Y/N].')
            choice=input()[0]
            if(choice=='y' or choice=='Y'):
                 with open(new_file, 'w') as output_file:
                    output_file.write(json.dumps(
           swagger_json,cls=TMCSerializer, sort_keys=True, indent=4, separators=(',', ': ')))
            else:
                 print('Exiting!!!')
                 exit()

        else: 
              with open(new_file, 'w') as output_file:
                   output_file.write(json.dumps(
           swagger_json,cls=TMCSerializer, sort_keys=True, indent=4, separators=(',', ': ')))
if __name__ == '__main__':
    main()