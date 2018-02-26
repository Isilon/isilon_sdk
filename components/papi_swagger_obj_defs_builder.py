"""Builds Swagger data model definitions using PAPI source docs."""

import argparse
import json
import modulefinder
import os
import re
import sys


def find_matching_obj_def(obj_defs, new_obj_def):
    """Find matching object definition."""
    for obj_name in obj_defs:
        existing_obj_def = obj_defs[obj_name]
        if "properties" in new_obj_def and "properties" in existing_obj_def:
            if new_obj_def["properties"] == existing_obj_def["properties"]:
                return obj_name
        elif "properties" not in existing_obj_def:
            print("**** No properties: {}".format(existing_obj_def))
    return None


def find_or_add_obj_def(obj_defs, new_obj_def, new_obj_name):
    """Reuse existing object definition if exists or add new one."""
    matching_obj = find_matching_obj_def(obj_defs, new_obj_def)
    if matching_obj is not None:
        return matching_obj

    obj_defs[new_obj_name] = new_obj_def
    return new_obj_name


def add_dependencies(module_dir, filename, modules):
    finder = modulefinder.ModuleFinder()
    finder.run_script(os.path.join(module_dir, filename))
    for module in finder.modules.values():
        # if the module comes from the module_dir then process it to get
        # its dependencies.
        if os.path.dirname(str(module.__file__)) == module_dir:
            mod_filename = os.path.basename(module.__file__)
            if mod_filename == filename:
                continue
            # if this module has not already been added then add it.
            if (mod_filename.endswith("_types.py")
                    or (mod_filename.find("_types_v") != -1
                        and mod_filename.endswith(".py"))):
                if mod_filename not in modules:
                    # add the modules that this module is dependent on
                    add_dependencies(module_dir, mod_filename, modules)
                    modules.append(mod_filename)


def build_module_list(filenames, module_dir, modules):
    for filename in filenames:
        if (filename.endswith("_types.py") or (
                filename.find("_types_v") != -1 and filename.endswith(".py"))):
            if filename not in modules:
                # add the modules that this module is dependent on
                add_dependencies(module_dir, filename, modules)
                modules.append(filename)


def find_best_type_for_prop(prop):
    multiple_types = prop["type"]
    # delete it so that we throw an exception if none of types
    # are non-"null"
    del prop["type"]

    for one_type in multiple_types:
        # sometimes the types are base types and sometimes they
        # are sub objects
        if isinstance(one_type, dict):
            if one_type["type"] == "null":
                continue

            if isinstance(one_type["type"], list):
                one_type = find_best_type_for_prop(one_type)
            prop = one_type

            # favor more specific types over "string"
            if prop["type"] != "string":
                break

        elif one_type != "null":
            prop["type"] = one_type
            break
    return prop


def plural_obj_name_to_singular(obj_name, post_fix="", post_fix_used=None):
    # if it's two 'ss' on the end then don't remove the last one
    if obj_name[-1] == 's' and obj_name[-2] != 's':
        # if container object ends with 's' then trim off the 's'
        # to (hopefully) create the singular version
        if obj_name[-3:] == 'ies':
            one_obj_name = obj_name[:-3].replace('_', '') + "y"
        else:
            one_obj_name = obj_name[:-1].replace('_', '')
    else:
        one_obj_name = obj_name.replace('_', '') + post_fix
        if post_fix_used is not None:
            post_fix_used.flag = True

    return one_obj_name


def add_if_new(full_obj_name, properties, prop_name, obj,
               isi_obj_names, isi_obj_list):
    if full_obj_name not in isi_obj_names:
        isi_obj_list.append((full_obj_name, properties, prop_name, obj))
        isi_obj_names[full_obj_name] = (properties, prop_name)


def isi_to_swagger_array_prop(prop, properties, prop_name, isi_obj_name,
                              isi_obj_list, isi_obj_names, obj_defs):

    if "items" not in prop:
        if "item" in prop:
            prop["items"] = prop["item"]
            del prop["item"]
        else:
            print("*** No items: {}_{} = {}".format(
                isi_obj_name, prop_name, properties[prop_name]))
            # string will kind of work for anything
            prop["items"] = {"type": "string"}

    if "type" in prop["items"] and prop["items"]["type"] == "object":
        item_obj_name = plural_obj_name_to_singular(prop_name, post_fix="Item")
        full_obj_name = isi_obj_name + "_" + item_obj_name
        add_if_new(
            full_obj_name, properties[prop_name], "items",
            prop["items"], isi_obj_names, isi_obj_list)

    elif ("type" in prop["items"]
          and isinstance(prop["items"]["type"], dict)
          and "type" in prop["items"]["type"]
          and prop["items"]["type"]["type"] == "object"):

        item_obj_name = plural_obj_name_to_singular(prop_name, post_fix="Item")
        full_obj_name = isi_obj_name + "_" + item_obj_name
        add_if_new(
            full_obj_name, properties[prop_name], "items",
            prop["items"]["type"], isi_obj_names, isi_obj_list)

    elif "type" in prop["items"] and isinstance(prop["items"]["type"], list):
        best_prop = find_best_type_for_prop(prop["items"])
        if "type" in best_prop and best_prop["type"] == "object":
            item_obj_name = plural_obj_name_to_singular(
                prop_name, post_fix="Item")
            full_obj_name = isi_obj_name + "_" + item_obj_name
            add_if_new(
                full_obj_name, properties[prop_name], "items",
                best_prop, isi_obj_names, isi_obj_list)
        else:
            properties[prop_name]["items"] = best_prop
    elif "type" in prop["items"] and prop["items"]["type"] == "array":
        isi_to_swagger_array_prop(
            prop["items"], properties[prop_name], "items",
            isi_obj_name, isi_obj_list, isi_obj_names, obj_defs)
    elif "type" not in prop["items"] and "$ref" not in prop["items"]:
        print("*** Array with no type or $ref: {}: {}".format(
            isi_obj_name, prop))
        # string will kind of work for anything
        prop["items"] = {"type": "string"}


def isi_to_swagger_object_def(isi_obj_name, isi_schema, obj_defs,
                              isi_obj_list, isi_obj_names):
    if "type" not in isi_schema:
        # have seen this for empty responses
        return "Empty"

    if isinstance(isi_schema["type"], list):
        for schema_list_item in isi_schema["type"]:
            if "type" not in schema_list_item:
                # hack - just return empty object
                return "Empty"
            # use the first single object schema (usually the "list" type) is
            # used to allow for multiple items to be created with a single
            # call.
            if schema_list_item["type"] == "object":
                isi_schema["type"] = "object"
                isi_schema["properties"] = schema_list_item["properties"]
                break

    if isi_schema["type"] != "object":
        raise RuntimeError(
            "isi_schema is not type 'object': {}".format(isi_schema))

    # found a few empty objects that omit the properties field
    if "properties" not in isi_schema:
        if "settings" in isi_schema:
            # saw this with /3/cluster/timezone
            isi_schema["properties"] = isi_schema["settings"]
            del isi_schema["settings"]
        else:
            isi_schema["properties"] = {}

    required_props = []
    for prop_name in isi_schema["properties"]:
        prop = isi_schema["properties"][prop_name]
        if "type" not in prop:
            continue # must be a $ref
        update_props = False
        # check if this prop is required
        if "required" in prop:
            if prop["required"]:
                required_props.append(prop_name)
            del prop["required"]
        # check if there are multiple types for this prop
        if isinstance(prop["type"], list):
            # swagger doesn't like lists for types
            # so use the first type that is not "null"
            prop = find_best_type_for_prop(prop)
            update_props = True

        if prop["type"] == "object":
            # save this object for later
            full_obj_name = isi_obj_name + "_" + prop_name
            add_if_new(
                full_obj_name, isi_schema["properties"], prop_name,
                prop, isi_obj_names, isi_obj_list)

        elif (isinstance(prop["type"], dict)
              and prop["type"]["type"] == "object"):
            full_obj_name = isi_obj_name + "_" + prop_name
            add_if_new(
                full_obj_name, isi_schema["properties"], prop_name,
                prop["type"], isi_obj_names, isi_obj_list)

        elif prop["type"] == "array":
            isi_to_swagger_array_prop(
                prop, isi_schema["properties"], prop_name,
                isi_obj_name, isi_obj_list, isi_obj_names, obj_defs)
        elif prop["type"] == "string" and "enum" in prop:
            new_enum = []
            for item in prop["enum"]:
                # swagger doesn't know how to interpret '@DEFAULT' values
                if item[0] != '@':
                    new_enum.append(item)
            if new_enum:
                prop["enum"] = new_enum
            else:
                del prop["enum"]
            update_props = True
        elif prop["type"] == "any":
            prop["type"] = "string"
            update_props = True
        elif prop["type"] == "int":
            print("*** Invalid prop type in object {} prop {}: {}".format(
                isi_obj_name, prop_name, prop))
            prop["type"] = "integer"
            update_props = True
        elif prop["type"] == "bool":
            print("*** Invalid prop type in object {} prop {}: {}".format(
                isi_obj_name, prop_name, prop))
            prop["type"] = "boolean"
            update_props = True

        if update_props is True:
            isi_schema["properties"][prop_name] = prop
            update_props = False

    # attach required props
    if required_props:
        isi_schema["required"] = required_props

    return find_or_add_obj_def(obj_defs, isi_schema, isi_obj_name)


def build_unique_name(module_name, obj_name, isi_obj_names, swag_objs=None):
    # check if there is already an object with this name and if so
    # use the module_name to make it unique
    swag_obj_name = obj_name.title().replace("_", "")
    while swag_obj_name in isi_obj_names:
        # check if there is a version number on the module
        matches = re.search('(.*)(_types_v)(\\d+)', module_name)
        if matches is not None:
            version = matches.group(3)
            # try adding the version number to the end
            swag_obj_name += "V" + version
            if swag_obj_name not in isi_obj_names:
                break
        else:
            version = ""
        if swag_objs is not None:
            # pull out the object whose name matched and update it
            existing_mod_name, existing_obj_name = isi_obj_names[swag_obj_name]
            existing_new_name = build_unique_name(
                existing_mod_name, existing_obj_name, isi_obj_names)
            del isi_obj_names[swag_obj_name]
            swag_objs[existing_new_name] = swag_objs[swag_obj_name]
            del swag_objs[swag_obj_name]
        # try prepending the module name
        swag_obj_namespace = module_name.replace(
            "_types", "").title().replace("_", "")
        swag_obj_name = swag_obj_namespace + swag_obj_name
        if swag_obj_name not in isi_obj_names:
            break
        else:
            # doesn't seem possible that i would get here, but just in case
            raise RuntimeError(
                "Unable to build unique name for {}: {} {}.".format(
                    module_name, obj_name, swag_obj_name))

    isi_obj_names[swag_obj_name] = (module_name, obj_name)
    return swag_obj_name


def main():
    argparser = argparse.ArgumentParser(
        description=("Builds Swagger data model definitions "
                     "using the PAPI source docs."))
    argparser.add_argument(
        "papiDocDir",
        help="Path to the isilon/lib/isi_platform_api/doc-inc directory.")
    argparser.add_argument("outputFile", help="Path to the output file.")

    args = argparser.parse_args()

    papiDocDir = os.path.abspath(args.papiDocDir)
    if os.path.exists(papiDocDir) is False:
        print("Invalid path: {}".format(papiDocDir))
        sys.exit(1)

    sys.path.append(papiDocDir)

    modules = []
    build_module_list(os.listdir(papiDocDir), papiDocDir, modules)

    swag_objs = {
        "Error": {
            "type": "object",
            "required": [
                "code",
                "message"
            ],
            "properties": {
                "code": {
                    "type": "integer",
                    "format": "int32"
                    },
                "message": {
                    "type": "string"
                }
            }
        },
        "Empty": {
            "type": "object",
            "properties": {}
        },
        "CreateResponse": {
            "properties": {
                "id": {
                    "description": ("ID of created item that can be used to "
                                    "refer to item in the collection-item "
                                    "resource path."),
                    "type": "string"
                }
            },
            "required": [
                "id"
            ],
            "type": "object"
        }
    }

    isi_objs = []
    # list of unique object names (prevent double processing)
    isi_obj_names = dict()
    # process top-level objects
    for module_filename in modules:
        module_name = os.path.splitext(module_filename)[0]
        module = __import__(module_name)
        for obj_name in dir(module):
            obj = getattr(module, obj_name)
            if (isinstance(obj, dict) and "type" in obj and
                    obj["type"] == "object"):
                # see if this object is already defined
                if find_matching_obj_def(swag_objs, obj) is None:
                    swag_obj_name = build_unique_name(
                        module_name, obj_name, isi_obj_names, swag_objs)

                    isi_to_swagger_object_def(
                        swag_obj_name, obj, swag_objs, isi_objs, isi_obj_names)

    # process objects referenced from inside other objects
    for obj_value in isi_objs:
        obj_name = obj_value[0]
        props = obj_value[1]
        prop_name = obj_value[2]
        obj = obj_value[3]

        ref_obj_name = isi_to_swagger_object_def(
            obj_name, obj, swag_objs, isi_objs, isi_obj_names)
        try:
            prop_description = props[prop_name]["description"]
        except KeyError:
            prop_description = ""
            if "description" in obj:
                prop_description = obj["description"]
            elif ref_obj_name != obj_name:
                # try to get the description from the ref'ed object
                ref_obj = swag_objs[ref_obj_name]
                if "description" in ref_obj:
                    prop_description = ref_obj["description"]

        props[prop_name] = {
            "description" : prop_description,
            "$ref" : "#/definitions/" + ref_obj_name
        }

    with open(args.outputFile, "w") as outputFile:
        outputFile.write(json.dumps(swag_objs, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
