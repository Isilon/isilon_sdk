import argparse
import json
import modulefinder
import os
import re
import sys


def FindMatchingObjDef(objDefs, newObjDef):
    for objName in objDefs:
        existingObjDef = objDefs[objName]
        if "properties" in newObjDef \
                and "properties" in existingObjDef:
            if newObjDef["properties"] == existingObjDef["properties"]:
                return objName
        elif "properties" not in existingObjDef:
            print >> sys.stderr, "**** No properties: " \
                    + str(existingObjDef) + "\n"
    return None


def FindOrAddObjDef(objDefs, newObjDef, newObjName):
    """
    Reuse existing object def if there's a match or add a new one
    """
    matchingObj = FindMatchingObjDef(objDefs, newObjDef)
    if matchingObj is not None:
        # print "Found match for " + newObjName + " = " + matchingObj
        return matchingObj
    # print "No match for " + newObjName
    objDefs[newObjName] = newObjDef
    return newObjName


def AddDependencies(modDir, fileName, modules):
    finder = modulefinder.ModuleFinder()
    finder.run_script(os.path.join(modDir, fileName))
    for module in finder.modules.values():
        # if the module comes from the modDir then process it to get
        # its dependencies.
        if os.path.dirname(str(module.__file__)) == modDir:
            modFileName = os.path.basename(module.__file__)
            if modFileName == fileName:
                continue
            # if this module has not already been added then add it.
            if modFileName.endswith("_types.py") \
                    or (modFileName.find("_types_v") != -1 \
                    and modFileName.endswith(".py")):
                if modFileName not in modules:
                    # add the modules that this module is dependent on
                    AddDependencies(modDir, modFileName, modules)
                    modules.append(modFileName)


def BuildModuleList(fileNames, modDir, modules):
    for fileName in fileNames:
        if fileName.endswith("_types.py") \
                or (fileName.find("_types_v") != -1 \
                and fileName.endswith(".py")):
            if fileName not in modules:
                # add the modules that this module is dependent on
                AddDependencies(modDir, fileName, modules)
                modules.append(fileName)


def FindBestTypeForProp(prop):
    multipleTypes = prop["type"]
    # delete it so that we throw an exception if none of types
    # are non-"null"
    del prop["type"]
    try:
        propDescription = prop["description"]
    except KeyError:
        propDescription = ""
    bestDictProp = None
    for oneType in multipleTypes:
        # sometimes the types are base types and sometimes they
        # are sub objects
        if type(oneType) == dict:
            if oneType["type"] == "null":
                continue
            if bestDictProp is None \
                    or bestDictProp["type"] == "string":
                # favor more specific types over "string"
                if type(oneType["type"]) == list:
                    # another list???
                    # TODO make this loop a recursive call
                    oneType = FindBestTypeForProp(oneType)
                bestDictProp = oneType
            prop = bestDictProp
            if prop["type"] != "string":
                break

        elif oneType != "null":
            prop["type"] = oneType
            break
    return prop


def PluralObjNameToSingular(objName, postFix="", postFixUsed=None):
    # if it's two 'ss' on the end then don't remove the last one
    if objName[-1] == 's' and objName[-2] != 's':
        # if container object ends with 's' then trim off the 's'
        # to (hopefully) create the singular version
        if objName[-3:] == 'ies':
            oneObjName = objName[:-3].replace('_', '') + "y"
        else:
            oneObjName = objName[:-1].replace('_', '')
    else:
        oneObjName = objName.replace('_', '') + postFix
        if postFixUsed is not None:
            postFixUsed.flag = True

    return oneObjName


def AddIfNew(
        fullObjName, properties, propName, obj,
        isiObjNames, isiObjList):
    if fullObjName not in isiObjNames:
        isiObjList.append((fullObjName,
            properties, propName, obj))
        isiObjNames[fullObjName] = (properties, propName)


def IsiArrayPropToSwaggerArrayProp(
        prop, properties, propName, isiObjName,
        isiObjList, isiObjNames, objDefs):

    if "items" not in prop:
        if "item" in prop:
            prop["items"] = prop["item"]
            del prop["item"]
        else:
            print >> sys.stderr, "*** No items: " \
                    + isiObjName + "_" + propName + " = " \
                    + str(properties[propName]) + "\n"
            # string will kind of work for anything
            prop["items"] = {"type": "string"}

    if "type" in prop["items"] and prop["items"]["type"] == "object":
        itemsObjName = PluralObjNameToSingular(propName,
                                               postFix="Item")
        fullObjName = isiObjName + "_" + itemsObjName
        AddIfNew(fullObjName,
                properties[propName], "items", prop["items"],
                isiObjNames, isiObjList)
        # print "Added object items %s.%s: %s" \
        #        % (isiObjName, propName, fullObjName)
    elif "type" in prop["items"] \
            and type(prop["items"]["type"]) == dict \
            and "type" in prop["items"]["type"] \
            and prop["items"]["type"]["type"] == "object":
        # WTF?
        itemsObjName = PluralObjNameToSingular(propName,
                                               postFix="Item")
        fullObjName = isiObjName + "_" + itemsObjName
        AddIfNew(fullObjName,
                properties[propName], "items", prop["items"]["type"],
                isiObjNames, isiObjList)
        # print "Added type items: " + fullObjName
    elif "type" in prop["items"] \
            and type(prop["items"]["type"]) == list:
        bestProp = FindBestTypeForProp(prop["items"])
        if "type" in bestProp and bestProp["type"] == "object":
            itemsObjName = PluralObjNameToSingular(propName,
                    postFix="Item")
            fullObjName = isiObjName + "_" + itemsObjName
            AddIfNew(fullObjName,
                    properties[propName], "items", bestProp,
                    isiObjNames, isiObjList)
        else:
            properties[propName]["items"] = bestProp
    elif "type" in prop["items"] \
            and prop["items"]["type"] == "array":
        IsiArrayPropToSwaggerArrayProp(prop["items"],
                properties[propName], "items", isiObjName,
                isiObjList, isiObjNames, objDefs)
    elif "type" not in prop["items"] and "$ref" not in prop["items"]:
        print >> sys.stderr, "*** Array with no type or $ref: " \
                + isiObjName + ": " + str(prop) + "\n"
        # string will kind of work for anything
        prop["items"] = {"type": "string"}



def IsiObjectToSwaggerObjectDef(
        isiObjName, isiSchema, objDefs, isiObjList, isiObjNames):
    if "type" not in isiSchema:
        # have seen this for empty responses
        return "Empty"

    if type(isiSchema["type"]) == list:
        for schemaListItem in isiSchema["type"]:
            if "type" not in schemaListItem:
                # hack - just return empty object
                return "Empty"
            # use the first single object schema (usually the "list" type) is
            # used to allow for multiple items to be created with a single
            # call.
            if schemaListItem["type"] == "object":
                isiSchema["type"] = "object"
                isiSchema["properties"] = schemaListItem["properties"]
                break

    if isiSchema["type"] != "object":
        raise RuntimeError("IsiSchema is not type 'object': "\
                + str(isiSchema))

    # found a few empty objects that omit the properties field
    if "properties" not in isiSchema:
        if "settings" in isiSchema:
            # saw this with /3/cluster/timezone
            isiSchema["properties"] = isiSchema["settings"]
            del isiSchema["settings"]
        else:
            isiSchema["properties"] = {}

    requiredProps = []
    for propName in isiSchema["properties"]:
        prop = isiSchema["properties"][propName]
        if "type" not in prop:
            continue # must be a $ref
        updateProps = False
        # check if this prop is required
        if "required" in prop:
            if  prop["required"] == True:
                requiredProps.append(propName)
            del prop["required"]
        # check if there are multiple types for this prop
        if type(prop["type"]) == list:
            # swagger doesn't like lists for types
            # so use the first type that is not "null"
            prop = FindBestTypeForProp(prop)
            updateProps = True

        if prop["type"] == "object":
            # save this object for later
            fullObjName = isiObjName + "_" + propName
            AddIfNew(fullObjName,
                    isiSchema["properties"], propName, prop,
                    isiObjNames, isiObjList)
            # print "Added " + fullObjName
        elif type(prop["type"]) == dict \
                and prop["type"]["type"] == "object":
            fullObjName = isiObjName + "_" + propName
            AddIfNew(fullObjName,
                    isiSchema["properties"], propName, prop["type"],
                    isiObjNames, isiObjList)
            # print "Added[%s.%s] = %s" % (isiObjName, propName, fullObjName)
        elif prop["type"] == "array":
            IsiArrayPropToSwaggerArrayProp(prop,
                    isiSchema["properties"], propName, isiObjName,
                    isiObjList, isiObjNames, objDefs)
        elif prop["type"] == "string" and "enum" in prop:
            newEnum = []
            for item in prop["enum"]:
                # swagger doesn't know how to interpret '@DEFAULT' values
                if item[0] != '@':
                    newEnum.append(item)
            if len(newEnum) > 0:
                prop["enum"] = newEnum
            else:
                del prop["enum"]
            updateProps = True
        elif prop["type"] == "any":
            prop["type"] = "string"
            updateProps = True
        elif prop["type"] == "int":
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["type"] = "integer"
            updateProps = True
        elif prop["type"] == "bool":
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["type"] = "boolean"
            updateProps = True

        if updateProps is True:
            isiSchema["properties"][propName] = prop
            updateProps = False


    # attache required props
    if len(requiredProps) > 0:
        isiSchema["required"] = requiredProps

    return FindOrAddObjDef(objDefs,
            isiSchema, isiObjName)


def BuildUniqueName(moduleName, objName, isiObjNames, swagObjs=None):
    # check if there is already an object with this name and if so
    # use the moduleName to make it unique
    swagObjName = objName.title().replace("_", "")
    while swagObjName in isiObjNames:
        # check if there is a version number on the module
        matches = re.search('(.*)(_types_v)(\\d+)', moduleName)
        if matches is not None:
            version = matches.group(3)
            # try adding the version number to the end
            swagObjName += "V" + version
            if swagObjName not in isiObjNames:
                break
        else:
            version = ""
        if swagObjs is not None:
            # pull out the object whose name matched and update it
            existingModName, existingObjName = isiObjNames[swagObjName]
            existingNewName = \
                    BuildUniqueName(
                            existingModName, existingObjName, isiObjNames)
            del isiObjNames[swagObjName]
            swagObjs[existingNewName] = swagObjs[swagObjName]
            del swagObjs[swagObjName]
        # try prepending the module name
        swagObjNameSpace = moduleName.replace("_types", "").title().replace("_", "")
        swagObjName = swagObjNameSpace + swagObjName
        if swagObjName not in isiObjNames:
            break
        else:
            # doesn't seem possible that i would get here, but just in case
            raise RuntimeError("Unable to build unique name for %s: %s %s." \
                    % (moduleName, objName, swagObjName))

    isiObjNames[swagObjName] = (moduleName, objName)
    return swagObjName


def main():
    argparser = argparse.ArgumentParser(
            description="Builds the Swagger data model definitions for the "\
                    "PAPI using the source docs.")
    argparser.add_argument("papiDocDir", help="Path to the "\
            "isilon/lig/isi_platform/api/doc-inc directory.")
    argparser.add_argument("outputFile", help="Path to the output file.")

    args = argparser.parse_args()

    # papiDocDir = \
    #        "/home/apecoraro/git/onefs-adv-dev/isilon/lib/isi_platform_api/doc-inc"
    papiDocDir = os.path.abspath(args.papiDocDir)
    if os.path.exists(papiDocDir) is False:
        print >> sys.stderr, "Invalid path: " + papiDocDir
        sys.exit(1)

    sys.path.append(papiDocDir)

    modules = []
    BuildModuleList(os.listdir(papiDocDir), papiDocDir, modules)
    # BuildModuleList(["smb_types_v3.py", "auth_types.py"], papiDocDir, modules)
    # BuildModuleList(["auth_types.py"], papiDocDir, modules)
    # BuildModuleList(["nfs_types_v1.py", "nfs_types_v2.py"], papiDocDir, modules)

    swagObjs = {
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
        "Empty": { "type": "object", "properties": { } },
        "CreateResponse": {
            "properties": {
                "id": {
                    "description": "ID of created item that can be used to refer to item in the collection-item resource path.",
                    "type": "string"
                    }
                },
            "required": [
                "id"
                ],
            "type": "object"
            }
        }

    isiObjs = []
    isiObjNames = dict() # list of unique object names (prevent double processing)
    # process top-level objects
    for moduleFileName in modules:
        moduleName = os.path.splitext(moduleFileName)[0]
        module = __import__(moduleName)
        for objName in dir(module):
            obj = getattr(module, objName)
            if type(obj) == dict and "type" in obj and obj["type"] == "object":
                # see if this object is already defined
                if FindMatchingObjDef(swagObjs, obj) is None:
                    swagObjName = BuildUniqueName(moduleName, objName, isiObjNames,
                            swagObjs)
                    # print "Adding " + swagObjName
                    IsiObjectToSwaggerObjectDef(swagObjName, obj, swagObjs,
                            isiObjs, isiObjNames)

    # process objects referenced from inside other objects
    for objValue in isiObjs:
        objName = objValue[0]
        props = objValue[1]
        propName = objValue[2]
        obj = objValue[3]
        # print "HandlingRef: " + objName
        refObjName = \
                IsiObjectToSwaggerObjectDef(
                        objName, obj, swagObjs, isiObjs, isiObjNames)
        try:
            propDescription = props[propName]["description"]
        except KeyError:
            propDescription = ""
            if "description" in obj:
                propDescription = obj["description"]
            elif refObjName != objName:
                # try to get the description from the ref'ed object
                refObj = swagObjs[refObjName]
                if "description" in refObj:
                    propDescription = refObj["description"]
        props[propName] = {
                "description" : propDescription,
                "$ref" : "#/definitions/" + refObjName}


    with open(args.outputFile, "w") as outputFile:
        outputFile.write(json.dumps(swagObjs, indent=4, sort_keys=True))

if __name__ == "__main__":
    main()
