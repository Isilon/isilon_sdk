#!/usr/bin/env python
"""
This script will print to stdout a swagger config based on the ?describe
responses from the PAPI handlers on your cluster (specified by cluster name or
ip address as the first argument to this script).  Swagger tools can now use
this config to create language bindings and documentation.
"""
import argparse
from collections import OrderedDict
import getpass
import json
import logging as log
import os
import re
import sys
import traceback

import requests
from requests.auth import HTTPBasicAuth

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
}

# list of url parameters that need to be url encoded, this hack works for now,
# but could cause problems if new params are added that are not unique.
URL_ENCODE_PARAMS = ['NfsAliasId']
# our extension to swagger which is used to generate code for doing the url
# encoding of the parameters specified above.
X_ISI_URL_ENCODE_PATH_PARAM = 'x-isi-url-encode-path-param'

# tracks swagger operations generated from URLs to ensure uniqueness
GENERATED_OPS = {}
SWAGGER_DEFS = {}


def onefs_short_version(host, port, auth):
    """Query a cluster and return the 2 major version digits"""
    url = 'https://{0}:{1}/platform/1/cluster/config'.format(host, port)
    config = requests.get(url, auth=auth, verify=False).json()
    release = config['onefs_version']['release'].strip('v')
    short_vers = '.'.join(release.split('.')[:2])
    return short_vers


def isi_props_to_swagger_params(isi_props, param_type):
    """Convert isi properties to Swagger parameters."""
    if not isi_props:
        return []
    swagger_parameters = []
    for isi_prop_name, isi_prop in isi_props.items():
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
        elif (obj_name[-4:] == 'ches' or obj_name[-5:] == 'iases'):
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
            break
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
            # XXX: bkrueger (8 Mar 2018) default to string if not defined
            prop['items'] = {'type': 'string'}

    # protect against Java array out of bounds exception
    if ('maxItems' in prop and prop['maxItems'] > 2147483642):
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
    elif ('type' in prop['items'] and prop['items']['type'] == 'array'):
        isi_to_swagger_array_prop(
            prop['items'], 'items', isi_obj_name, isi_obj_name_space,
            isi_schema_props[prop_name], class_ext_post_fix,
            is_response_object)
    elif 'type' in prop['items']:
        if prop['items']['type'] == 'any' or prop['items']['type'] == 'string':
            # Swagger does not support 'any'
            if prop['items']['type'] == 'any':
                prop['items']['type'] = 'string'
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
            schema_copy = isi_schema.copy()
            for key in isi_schema.keys():
                del isi_schema[key]
            isi_schema['properties'] = schema_copy
        else:
            log.warning(("Invalid schema for object %s, no 'type' specified. "
                         "Adding 'type': 'object'."), isi_obj_name)
        isi_schema['type'] = 'object'

    if isinstance(isi_schema['type'], list):
        for schema_list_item in isi_schema['type']:
            if schema_list_item is None:
                log.warning("Found null object in JSON schema list")
                continue
            if 'type' not in schema_list_item:
                # hack - just return empty object
                return '#/definitions/Empty'
            # As of OneFS 8.1.0, the response body schema may be a list where
            # the first object in the list is the errors object and the second
            # object in the list is the success object. Thus, this loop will
            # iterate until it has assigned the properties from the last
            # object in the list.
            if schema_list_item['type'] == 'object':
                isi_schema = schema_list_item

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
    # Issue #12: Correct misspellings
    if sub_obj_namespace == 'DebugStatsUnknown':
        if 'descriprion' in isi_schema:
            isi_schema['description'] = isi_schema['descriprion']
            del isi_schema['descriprion']
            log.warning("Found 'description' misspelled as 'descriprion'")
    # Issue #13: Correct properties schema
    elif sub_obj_namespace == 'StatisticsOperation':
        if 'operations' in isi_schema['properties']:
            operations = isi_schema['properties']['operations'][0]['operation']
            if operations['required']:
                isi_schema['required'] = True
            isi_schema['properties']['operation'] = operations
            del isi_schema['properties']['operations']
            log.warning("Replace 'operations' property with 'operation'")
    elif (sub_obj_namespace.startswith('StoragepoolNodepool') or
          sub_obj_namespace.startswith('StoragepoolStoragepool')):
        if 'health_flags' in isi_schema:
            isi_schema['properties']['health_flags'] = \
                isi_schema['health_flags']
            del isi_schema['health_flags']
            log.warning("Move 'health_flags' property under 'properties'")

    required_props = []
    for prop_name, prop in isi_schema['properties'].items():

        # Issue #8: Remove invalid placement of required field
        if (sub_obj_namespace == 'StoragepoolStatusUnhealthyItem' and
                prop_name == 'health_flags'):
            if 'required' in prop['items']:
                del prop['items']['required']
                log.warning("Remove 'required' from array items")
        # Issue #9: Remove duplicate `delete_child`
        elif ((sub_obj_namespace == (
                'SmbSettingsGlobalSettingsAuditGlobalSaclItem')
               or sub_obj_namespace == 'SmbSettingsGlobalAuditGlobalSaclItem')
              and prop_name == 'permission'):
            if 'items' in prop and 'enum' in prop['items']:
                prop['items']['enum'] = (
                    list(OrderedDict.fromkeys(prop['items']['enum'])))
                log.warning("Remove duplicate 'delete_child' from enum")
        # Issue #10: Update required field to draft 4 style
        elif (sub_obj_namespace.startswith('Job') and 'items' in prop and
              'required' in prop['items']):
            if prop['items']['required']:
                if (is_response_object is False or
                        not isinstance(prop['type'], list)):
                    required_props.append(prop_name)
            del prop['items']['required']
            log.warning("Update 'required' field to draft 4 style")
        # Issue #12: Correct misspellings
        elif sub_obj_namespace == 'AuthAccessAccessItem' and prop_name == 'id':
            if 'descriptoin' in prop:
                prop['description'] = prop['descriptoin']
                del prop['descriptoin']
                log.warning("Found 'description' misspelled as 'descriptoin'")
        elif sub_obj_namespace.startswith('DebugStats'):
            if 'descriprion' in prop:
                prop['description'] = prop['descriprion']
                del prop['descriprion']
                log.warning("Found 'description' misspelled as 'descriprion'")
        elif sub_obj_namespace.startswith('HealthcheckEvaluation'):
            if prop_name == 'run_status' and 'desciption' in prop:
                prop['description'] = prop['desciption']
                del prop['desciption']
                log.warning("Found 'description' misspelled as 'desciption'")
        elif 'Subnet' in sub_obj_namespace:
            if prop_name == 'sc_service_name' and 'description:' in prop:
                prop['description'] = prop['description:']
                del prop['description:']
                log.warning("Found 'description' misspelled as 'description:'")
        # Issue #14: Include hardware `devices` fields
        elif sub_obj_namespace == 'HardwareTapes' and prop_name == 'devices':
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
        elif (sub_obj_namespace == (
                'EventEventgroupOccurrencesEventgroup-Occurrence') and
              prop_name == 'causes'):
            if 'type' in prop['items']:
                prop['items'] = prop['items']['type']
                prop['type'] = 'array'
                log.warning("Correct nested array schema in 'causes' property")
        # Remove custom `ignore_case` field
        elif sub_obj_namespace.startswith('EventAlertCondition'):
            if 'ignore_case' in prop:
                del prop['ignore_case']
            if 'items' in prop and 'ignore_case' in prop['items']:
                del prop['items']['ignore_case']
            log.warning("Remove custom 'ignore_case' field")
        elif sub_obj_namespace == 'HistogramStatByBreakout':
            if prop_name == 'data' and prop['type'] == 'array':
                if 'properties' in prop:
                    del prop['properties']
                    prop['items'] = {
                        'type': 'array',
                        'items': {'type': 'integer'}
                    }
                    log.warning("Correct 'data' properties array object")
        elif sub_obj_namespace.startswith('Ndmp'):
            if prop['type'] == 'array' and 'properties' in prop:
                prop['items'] = {
                    'type': 'object',
                    'properties': prop['properties']
                }
                del prop['properties']
                log.warning("Move 'properties' into the 'items' object")
        elif sub_obj_namespace.startswith('SummaryProtocolStatsProtocol'):
            if 'type' not in prop:
                prop_copy = prop.copy()
                for key in prop.keys():
                    del prop[key]
                prop['properties'] = prop_copy
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
        elif sub_obj_namespace == 'HardwareFcportsNode':
            if (prop_name == 'fcports' and prop['type'] == 'array' and
                    'properties' in prop):
                prop['items'] = prop['properties']
                del prop['properties']
                log.warning("Move 'fcports' array properties into 'items'")

        if 'type' not in prop:
            if 'enum' in prop:
                log.warning(('Invalid enum prop with no type in object %s '
                             'prop %s: %s'), isi_obj_name, prop_name, prop)
                prop['type'] = 'string'
            else:
                continue  # must be a $ref
        if 'required' in prop:
            if prop['required'] is True:
                # Often the PAPI will have a required field whose value can be
                # either a real value, such as a string, or it can be a null,
                # which Swagger can not deal with. This is only problematic
                # in objects that are returned as a response because it ends up
                # causing the Swagger code to throw an exception upon receiving
                # a PAPI response that contains null values for the 'required'
                # fields. So if the type is a multi-type (i.e. list) and
                # is_response_object is True, then we don't add the field to
                # the list of required fields.
                if (is_response_object is False or
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
                elif item[0] != '@':
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

    # attach required props
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

        for prop_name, prop in existing_props.items():
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
            for sub_index in reversed(range(index)):
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
    for index in reversed(range(len(names) - 1)):
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

    if 'POST_input_schema' in isi_desc_json:
        post_input_schema = isi_desc_json['POST_input_schema']
    else:
        post_input_schema = None
    if 'POST_output_schema' in isi_desc_json:
        post_resp_schema = isi_desc_json['POST_output_schema']
    else:
        post_resp_schema = None
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


def get_endpoint_paths(source_node_or_cluster, papi_port, base_url, auth,
                       exclude_end_points):
    """
    Gets the full list of PAPI URIs reported by source_node_or_cluster using
    the ?describe&list&json query arguments at the root level.
    Returns the URIs as a list of tuples where collection resources appear as
    (<collection-uri>, <single-item-uri>) and non-collection/static resources
    appear as (<uri>,None).
    """
    desc_list_parms = {'describe': '', 'json': '', 'list': ''}
    url = 'https://' + source_node_or_cluster + ':' + papi_port + base_url
    resp = requests.get(
        url=url, params=desc_list_parms, auth=auth, verify=False)
    end_point_list_json = json.loads(resp.text)

    base_end_points = {}
    end_point_paths = []
    ep_index = 0
    num_endpoints = len(end_point_list_json['directory'])
    while ep_index < num_endpoints:
        current_endpoint = end_point_list_json['directory'][ep_index]
        if current_endpoint[2] != '/':
            # skip floating point version numbers
            ep_index += 1
            continue

        next_ep_index = ep_index + 1
        while next_ep_index < num_endpoints:
            next_endpoint = end_point_list_json['directory'][next_ep_index]
            # strip off the version and compare to see if they are
            # the same.
            if next_endpoint[2:] != current_endpoint[2:]:
                # using current_endpoint
                break
            # skipping current_endpoint
            current_endpoint = next_endpoint
            ep_index = next_ep_index
            next_ep_index += 1

        if current_endpoint in exclude_end_points:
            ep_index += 1
            continue

        if current_endpoint[-1] != '>':
            base_end_points[current_endpoint[2:]] = (current_endpoint, None)
        else:
            try:
                item_endpoint = current_endpoint
                last_slash = item_endpoint.rfind('/')
                base_end_point_tuple = \
                    base_end_points[item_endpoint[2:last_slash]]
                base_end_point_tuple = (base_end_point_tuple[0], item_endpoint)
                end_point_paths.append(base_end_point_tuple)
                del base_end_points[item_endpoint[2:last_slash]]
            except KeyError:
                # no base for this item_endpoint
                end_point_paths.append((None, item_endpoint))

        ep_index += 1

    # remaining base end points have no item end point
    for base_end_point_tuple in base_end_points.values():
        end_point_paths.append(base_end_point_tuple)

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

    return sorted(end_point_paths, cmp=end_point_path_compare)


def main():
    """Main method for create_swagger_config executable."""

    argparser = argparse.ArgumentParser(
        description='Builds Swagger config from PAPI end point descriptions.')
    argparser.add_argument(
        '-i', '--input', dest='host',
        help='IP-address or hostname of the Isilon cluster to use as input.',
        action='store')
    argparser.add_argument(
        '-o', '--output', dest='output_file',
        help='Path to the output file.', action='store')
    argparser.add_argument(
        '-u', '--username', dest='username',
        help='The username to use for the cluster.',
        action='store', default=None)
    argparser.add_argument(
        '-p', '--password', dest='password',
        help='The password to use for the cluster.',
        action='store', default=None)
    argparser.add_argument(
        '-d', '--defs', dest='defs_file',
        help='Path to file with pre-built Swagger data model definitions.',
        action='store', default=None)
    argparser.add_argument(
        '-t', '--test', dest='test',
        help='Test mode on.', action='store_true', default=False)
    argparser.add_argument(
        '-l', '--logging', dest='log_level',
        help='Logging verbosity level', action='store', default='INFO')

    args = argparser.parse_args()

    log.basicConfig(
        format='%(asctime)s %(levelname)s - %(message)s',
        datefmt='%I:%M:%S', level=getattr(log, args.log_level.upper()))

    if args.username is None:
        args.username = raw_input(
            'Please provide the username used to access {} via PAPI: '.format(
                args.host))
    if args.password is None:
        args.password = getpass.getpass('Password: ')

    swagger_json = {
        'swagger': '2.0',
        'info': {
            'version': '0.1.11',
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
            'basic_auth': {
                'type': 'basic'
            }
        },
        'security': [{'basic_auth': []}],
        'paths': {},
        'definitions': {}
    }

    if args.defs_file:
        with open(args.defs_file, 'r') as def_file:
            SWAGGER_DEFS.update(json.loads(def_file.read()))
    else:
        SWAGGER_DEFS.update({
            'Error': {
                'type': 'object',
                'required': [
                    'code',
                    'message'
                ],
                'properties': {
                    'code': {
                        'type': 'integer',
                        'format': 'int32'
                    },
                    'message': {
                        'type': 'string'
                    }
                }
            },
            'Empty': {
                'type': 'object',
                'properties': {}
            },
            'CreateResponse': {
                'properties': {
                    'id': {
                        'description': ('ID of created item that can be used '
                                        'to refer to item in the collection-'
                                        'item resource path.'),
                        'maxLength': 255,
                        'minLength': 0,
                        'type': 'string'
                    }
                },
                'required': [
                    'id'
                ],
                'type': 'object'
            }
        })

    swagger_json['definitions'] = SWAGGER_DEFS

    auth = HTTPBasicAuth(args.username, args.password)
    base_url = '/platform'
    papi_port = '8080'
    desc_parms = {'describe': '', 'json': ''}

    swagger_json['info']['version'] = onefs_short_version(
        args.host, papi_port, auth)

    if swagger_json['info']['version'] in ['7.2', '8.0']:
        id_prop = SWAGGER_DEFS['CreateResponse']['properties']['id']
        del id_prop['maxLength']
        del id_prop['minLength']

    if not args.test:
        if swagger_json['info']['version'][0] == '7':
            exclude_end_points = [
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
            ]
        else:
            exclude_end_points = [
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
            ]

        end_point_paths = get_endpoint_paths(
            args.host, papi_port, base_url, auth, exclude_end_points)
    else:
        exclude_end_points = []
        end_point_paths = [
            ('/3/hardware/fcports', None),
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
            url = 'https://{}:{}{}{}'.format(
                args.host, papi_port, base_url, item_end_point_path)
            resp = requests.get(
                url=url, params=desc_parms, auth=auth, verify=False)

            item_resp_json = json.loads(resp.text)

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
            url = 'https://{}:{}{}{}'.format(
                args.host, papi_port, base_url, base_end_point_path)
            resp = requests.get(
                url=url, params=desc_parms, auth=auth, verify=False)
            base_resp_json = json.loads(resp.text)
            base_path_params = parse_path_params(base_end_point_path)
            base_path = {}
            # start with base path POST because it defines the base
            # creation object model
            try:
                if 'POST_args' in base_resp_json:
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

    with open(args.output_file, 'w') as output_file:
        output_file.write(json.dumps(
            swagger_json, sort_keys=True, indent=4, separators=(',', ': ')))


if __name__ == '__main__':
    main()
