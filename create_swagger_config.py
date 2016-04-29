#!/usr/bin/python
"""
This script will print to stdout a swagger config based on the ?describe
responses from the PAPI handlers on your cluster (specified by cluster name or
ip address as the first argument to this script).  Swagger tools can now use
this config to create language bindings and documentation.
"""
import argparse
import json
import getpass
import os
import re
import requests
from requests.auth import HTTPBasicAuth
import sys

requests.packages.urllib3.disable_warnings()

k_swaggerParamIsiPropCommonFields = [
    "description", "required", "type", "default", "maximum", "minimum", "enum",
    "items"]

def IsiPropsToSwaggerParams(isiProps, paramType):
    if len(isiProps) == 0:
        return []
    swaggerParameters = []
    for isiPropName in isiProps:
        # build a swagger param for each isi property
        swaggerParam = {}
        swaggerParam["in"] = paramType
        swaggerParam["name"] = isiPropName
        isiProp = isiProps[isiPropName]
        # attach common fields
        for fieldName in isiProp:
            if fieldName not in k_swaggerParamIsiPropCommonFields:
                print >> sys.stderr, "WARNING: " + fieldName + " not " \
                        "defined for Swagger in prop: " + str(isiProp)
                continue
            if fieldName == "type":
                if isiProp[fieldName] == "int":
                    # HACK fix for bugs in the PAPI
                    print >> sys.stderr, "*** Invalid type in params " \
                            + "of type " + str(paramType) + ": " \
                            + str(isiProps)
                    isiProp[fieldName] = "integer"
                elif isiProp[fieldName] == "bool":
                    # HACK fix for bugs in the PAPI
                    print >> sys.stderr, "*** Invalid type in params " \
                            + "of type " + str(paramType) + ": " \
                            + str(isiProps)
                    isiProp[fieldName] = "boolean"
            swaggerParam[fieldName] = isiProp[fieldName]
        # add the new param to the list of params
        swaggerParameters.append(swaggerParam)
    return swaggerParameters


class PostFixUsed:
    flag = False


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


def FindBestTypeForProp(prop):
    multipleTypes = prop["type"]
    # delete it so that we throw an exception if none of types
    # are non-"null"
    del prop["type"]
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


def IsiArrayPropToSwaggerArrayProp(
        prop, propName,
        isiObjName, isiObjNameSpace, isiSchemaProps, objDefs, classExtPostFix):

    if "items" not in prop and "item" in prop:
        prop["items"] = prop["item"]
        del prop["item"]

    if "type" in prop["items"] and prop["items"]["type"] == "object":
        itemsObjName = PluralObjNameToSingular(propName.title(),
                                               postFix="Item")
        if itemsObjName == isiObjName \
                or itemsObjName == PluralObjNameToSingular(isiObjName):
            # HACK don't duplicate the object name if the singular version of
            # this property is the same as the singular version of the
            # object name.
            itemsObjNameSpace = isiObjNameSpace
        else:
            itemsObjNameSpace = isiObjNameSpace + isiObjName
        # store the description in the ref for property object refs
        if "description" in prop["items"]:
            propDescription = prop["items"]["description"]
            del prop["items"]["description"]
        else:
            propDescription = ""

        objRef = IsiSchemaToSwaggerObjectDefs(
                    itemsObjNameSpace, itemsObjName,
                    prop["items"], objDefs,
                    classExtPostFix)
        isiSchemaProps[propName]["items"] = \
                {"description" : propDescription, "$ref" : objRef}
    elif "type" in prop["items"] \
            and type(prop["items"]["type"]) == dict \
            and "type" in prop["items"]["type"] \
            and prop["items"]["type"]["type"] == "object":
        # WTF?
        itemsObjName = PluralObjNameToSingular(propName.title(),
                                               postFix="Item")
        if itemsObjName == isiObjName \
                or itemsObjName == PluralObjNameToSingular(isiObjName):
            # HACK don't duplicate the object name if the singular version of
            # this property is the same as the singular version of the
            # object name.
            itemsObjNameSpace = isiObjNameSpace
        else:
            itemsObjNameSpace = isiObjNameSpace + isiObjName
        # store the description in the ref for property object refs
        objRef = IsiSchemaToSwaggerObjectDefs(
                    itemsObjNameSpace, itemsObjName,
                    prop["items"]["type"], objDefs,
                    classExtPostFix)
        isiSchemaProps[propName]["items"] = {"$ref" : objRef}
    elif "type" in prop["items"] \
            and type(prop["items"]["type"]) == list:
        prop["items"] = isiSchemaProps[propName]["items"] = \
                FindBestTypeForProp(prop["items"])
    elif "type" in prop["items"] \
            and prop["items"]["type"] == "array":
        IsiArrayPropToSwaggerArrayProp(prop["items"], "items",
                isiObjName, isiObjNameSpace, isiSchemaProps[propName],
                objDefs, classExtPostFix)
    elif "type" in prop["items"]:
        if prop["items"]["type"] == "any":
            # Swagger does not support "any"
            prop["items"]["type"] = "string"
        elif prop["items"]["type"] == "int":
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["items"]["type"] = "integer"
        elif prop["items"]["type"] == "bool":
            # HACK fix for bugs in the PAPI
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["items"]["type"] = "boolean"
    elif "type" not in prop["items"] and "$ref" not in prop["items"]:
        raise RuntimeError("Array with no type or $ref: " + str(prop))


def IsiSchemaToSwaggerObjectDefs(
        isiObjNameSpace, isiObjName, isiSchema, objDefs,
        classExtPostFix="Extended"):
    # converts isiSchema to a single schema with "#ref" for sub-objects
    # which is what Swagger expects. Adds the sub-objects to the objDefs
    # list.
    if "type" not in isiSchema:
        # have seen this for empty responses
        return "#/definitions/Empty"

    if type(isiSchema["type"]) == list:
        for schemaListItem in isiSchema["type"]:
            if "type" not in schemaListItem:
                # hack - just return empty object
                return "#/definitions/Empty"
            # use the first single object schema (usually the "list" type) is
            # used to allow for multiple items to be created with a single
            # call.
            if schemaListItem["type"] == "object":
                isiSchema["type"] = "object"
                isiSchema["properties"] = schemaListItem["properties"]
                break

    if isiSchema["type"] != "object":
        raise RuntimeError("Isi Schema is not type 'object': "\
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
        if "required" in prop:
            if prop["required"] == True:
                requiredProps.append(propName)
            del prop["required"]

        if type(prop["type"]) == list:
            # swagger doesn't like lists for types
            # so use the first type that is not "null"
            prop = isiSchema["properties"][propName] = \
                    FindBestTypeForProp(prop)

        if prop["type"] == "object":
            subObjNameSpace = isiObjNameSpace + isiObjName
            subObjName = propName.title().replace('_', '')
            # store the description in the ref for property object refs
            if "description" in prop:
                propDescription = prop["description"]
                del prop["description"]
            else:
                propDescription = ""

            objRef = IsiSchemaToSwaggerObjectDefs(
                        subObjNameSpace, subObjName, prop, objDefs,
                        classExtPostFix)
            isiSchema["properties"][propName] = \
                    {"description" : propDescription, "$ref" : objRef}
        elif type(prop["type"]) == dict \
                and prop["type"]["type"] == "object":
            subObjNameSpace = isiObjNameSpace + isiObjName
            subObjName = propName.title().replace('_', '')
            # store the description in the ref for property object refs
            if "description" in prop:
                propDescription = prop["description"]
                del prop["description"]
            else:
                propDescription = ""

            objRef = IsiSchemaToSwaggerObjectDefs(
                        subObjNameSpace, subObjName, prop["type"], objDefs,
                        classExtPostFix)
            isiSchema["properties"][propName] = \
                    {"description" : propDescription, "$ref" : objRef}
        elif prop["type"] == "array":
            IsiArrayPropToSwaggerArrayProp(prop, propName,
                    isiObjName, isiObjNameSpace, isiSchema["properties"],
                    objDefs, classExtPostFix)
            # code below is work around for bug in /auth/access/<USER> end point
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
        elif prop["type"] == "any":
            # Swagger does not support "any"
            prop["type"] = "string"
        elif prop["type"] == "int":
            # HACK fix for bugs in the PAPI
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["type"] = "integer"
        elif prop["type"] == "bool":
            # HACK fix for bugs in the PAPI
            print >> sys.stderr, "*** Invalid prop type in object " \
                    + isiObjName + " prop " + propName + ": " \
                    + str(prop) + "\n"
            prop["type"] = "boolean"

    # attache required props
    if len(requiredProps) > 0:
        isiSchema["required"] = requiredProps

    return FindOrAddObjDef(objDefs,
            isiSchema, isiObjNameSpace + isiObjName, classExtPostFix)


def FindOrAddObjDef(objDefs, newObjDef, newObjName, classExtPostFix):
    """
    Reuse existing object def if there's a match or add a new one
    Return the "definitions" path
    """
    for objName in objDefs:
        existingObjDef = objDefs[objName]
        if "allOf" in existingObjDef:
            continue #skip subclasses
        if newObjDef["properties"] == existingObjDef["properties"]:
            return "#/definitions/" + objName

    if newObjName in objDefs:
        # TODO at this point the subclass mechanism depends on the data models
        # being generated in the correct order, where base classes are
        # generated before sub classes. This is done by processing the
        # endpoints in order: POST base endpoint, all item endpoints, GET base
        # endpoint. This seems to work for nfs exports, obviously won't work if
        # the same pattern that nfs exports uses is not repeated by the other
        # endpoints.
        # crude/limited subclass generation
        existingObj = objDefs[newObjName]
        if "allOf" in existingObj:
            existingProps = existingObj["allOf"][-1]["properties"]
        else:
            existingProps = objDefs[newObjName]["properties"]
        extendedObjDef = \
                { "allOf" : [ { "$ref": "#/definitions/" + newObjName } ] }
        uniqueProps = {}
        for propName in newObjDef["properties"]:
            # delete properties that are shared.
            if propName not in existingProps:
                uniqueProps[propName] = newObjDef["properties"][propName]
        newObjDef["properties"] = uniqueProps
        extendedObjDef["allOf"].append(newObjDef)
        newObjName += classExtPostFix
        objDefs[newObjName] = extendedObjDef
    else:
        objDefs[newObjName] = newObjDef
    return "#/definitions/" + newObjName


def EndPointPathToApiObjName(endPoint):
    """
    Convert the end point url to an object and api name.
    """
    if endPoint[0] == '/':
        endPoint = endPoint[1:]
    names = endPoint.split("/")
    # discard the version
    del names[0]
    # use the first part of the path after the version
    isiApiName = re.sub('[^0-9a-zA-Z]+', '', names[0].title())
    if len(names) == 2:
        isiObjNameSpace = isiApiName
    elif len(names) == 1:
        isiObjNameSpace = ""
        isiObjName = isiApiName
        return isiApiName, isiObjNameSpace, isiObjName
    else:
        isiObjNameSpace = re.sub('[^0-9a-zA-Z]+', '', names[1].title())
        del names[0]
    del names[0]
    if len(names) == 0:
        isiObjName = isiObjNameSpace
    else:
        isiObjName = ""
        for name in names:
            isiObjName += re.sub('[^0-9a-zA-Z]+', '', name.title())
    return isiApiName, isiObjNameSpace, isiObjName


def ToSwaggerEndPoint(endPointPath):
    newEndPointPath = "/"
    for partialPath in endPointPath.split("/"):
        inputParam = partialPath.replace('<', '{').replace('>', '}')
        if inputParam != partialPath:
            partialPath = inputParam.title()
        newEndPointPath = os.path.join(newEndPointPath, partialPath)
    return newEndPointPath


def CreateSwaggerOperation(
        isiApiName, isiObjNameSpace, isiObjName, operation,
        isiInputArgs, isiInputSchema, isiRespSchema, objDefs,
        inputSchemaParamObjName=None,
        classExtPostFix="Extended"):
    # create a swagger operation object
    swaggerOperation = {}
    swaggerOperation["tags"] = [isiApiName]
    swaggerOperation["description"] = isiInputArgs["description"]
    if "properties" in isiInputArgs:
        swaggerParamType = "query" # pretty sure PAPI only uses url query params
        swaggerParams = \
                IsiPropsToSwaggerParams(isiInputArgs["properties"],
                                        swaggerParamType)
    else:
        swaggerParams = []

    swaggerOperation["operationId"] = operation + isiObjNameSpace + isiObjName

    if isiInputSchema is not None:
        # sometimes the url parameter gets same name, so the
        # inputSchemaParamObjName variable is used to prevent that
        if inputSchemaParamObjName is None:
            inputSchemaParamObjName = isiObjName
        objRef = IsiSchemaToSwaggerObjectDefs(
                    isiObjNameSpace, inputSchemaParamObjName,
                    isiInputSchema, objDefs,
                    classExtPostFix)
        inputSchemaParam = {}
        inputSchemaParam["in"] = "body"
        inputSchemaParam["name"] = isiObjNameSpace + inputSchemaParamObjName
        inputSchemaParam["required"] = True
        inputSchemaParam["schema"] = { "$ref": objRef }
        swaggerParams.append(inputSchemaParam)
        # just use the operation for the response because it seems like all the
        # responses to POST have the same schema
        isiRespObjNameSpace = operation[0].upper() + operation[1:] \
                + isiObjNameSpace
        isiRespObjName = isiObjName + "Response"
    else:
        isiRespObjNameSpace = isiObjNameSpace
        isiRespObjName = isiObjName

    swaggerOperation["parameters"] = swaggerParams

    # create responses
    swaggerResponses = {}
    if isiRespSchema is not None:
        objRef = IsiSchemaToSwaggerObjectDefs(
                    isiRespObjNameSpace, isiRespObjName, isiRespSchema,
                    objDefs, classExtPostFix)
        # create 200 response
        swagger200Resp = {}
        swagger200Resp["description"] = isiInputArgs["description"]
        swagger200Resp["schema"] = { "$ref": objRef }
        # add to responses
        swaggerResponses["200"] = swagger200Resp
    else:
        # if no response schema then default response is 204
        swagger204Resp = {}
        swagger204Resp["description"] = "Success."
        swaggerResponses["204"] = swagger204Resp
    # create default "error" response
    swaggerErrorResp = {}
    swaggerErrorResp["description"] = "Unexpected error"
    swaggerErrorResp["schema"] = { "$ref": "#/definitions/Error" }
    # add to responses
    swaggerResponses["default"] = swaggerErrorResp
    # add responses to the operation
    swaggerOperation["responses"] = swaggerResponses

    return swaggerOperation


def AddPathParams(swaggerParams, extraPathParams):
    for paramName, paramType in extraPathParams:
        pathParam = {}
        pathParam["name"] = paramName
        pathParam["in"] = "path"
        pathParam["required"] = True
        pathParam["type"] = paramType
        swaggerParams.append(pathParam)


def IsiPostBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, isiPathParams,
        objDefs):
    swaggerPath = {}
    isiPostArgs = isiDescJson["POST_args"]
    oneObjName = PluralObjNameToSingular(isiObjName, postFix="Item")

    if "POST_input_schema" in isiDescJson:
        postInputSchema = isiDescJson["POST_input_schema"]
    else:
        postInputSchema = None
    if "POST_output_schema" in isiDescJson:
        postRespSchema = isiDescJson["POST_output_schema"]
    else:
        postRespSchema = None
    operation = "create"
    swaggerPath["post"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, oneObjName, operation,
                    isiPostArgs, postInputSchema, postRespSchema, objDefs,
                    None, "CreateParams")
    AddPathParams(swaggerPath["post"]["parameters"], isiPathParams)

    return swaggerPath


def IsiPutBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, isiPathParams,
        objDefs):
    swaggerPath = {}
    inputArgs = isiDescJson["PUT_args"]

    inputSchema = isiDescJson["PUT_input_schema"]
    operation = "update"
    swaggerPath["put"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, isiObjName, operation,
                    inputArgs, inputSchema, None, objDefs)
    AddPathParams(swaggerPath["put"]["parameters"], isiPathParams)

    return swaggerPath


def IsiDeleteBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, isiPathParams,
        objDefs):
    swaggerPath = {}
    inputArgs = isiDescJson["DELETE_args"]
    operation = "delete"
    swaggerPath["delete"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, isiObjName, operation,
                    inputArgs, None, None, objDefs)
    AddPathParams(swaggerPath["delete"]["parameters"], isiPathParams)

    return swaggerPath


def IsiGetBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, isiPathParams,
        objDefs):
    swaggerPath = {}
    isiGetArgs = isiDescJson["GET_args"]
    getRespSchema = isiDescJson["GET_output_schema"]
    if "POST_args" in isiDescJson:
        operation = "list"
    else:
        # if no POST then this is a singleton so use "get" for operation
        operation = "get"
    swaggerPath["get"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, isiObjName, operation,
                    isiGetArgs, None, getRespSchema, objDefs)
    AddPathParams(swaggerPath["get"]["parameters"], isiPathParams)

    return swaggerPath


def IsiItemEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson,
        singleObjPostFix, itemInputType, extraPathParams,
        objDefs):
    swaggerPath = {}
    # first deal with POST and PUT in order to create the objects that are used
    # in the GET
    postFixUsed = PostFixUsed()
    oneObjName = PluralObjNameToSingular(isiObjName,
                                         postFix=singleObjPostFix,
                                         postFixUsed=postFixUsed)
    # if the singleObjPostFix was not used to make it singular then add "Id"
    # to itemId param name
    if postFixUsed.flag is False:
        itemId = isiObjNameSpace + oneObjName + "Id"
        # use default name of isiObjNameSpace + oneObjName
        inputSchemaParamObjName = None
    else:
        itemId = isiObjNameSpace + oneObjName
        inputSchemaParamObjName = oneObjName + "Params"
    itemIdUrl = "/{" + itemId + "}"
    itemIdParam = {}
    itemIdParam["name"] = itemId
    itemIdParam["in"] = "path"
    itemIdParam["required"] = True
    itemIdParam["type"] = itemInputType

    if "PUT_args" in isiDescJson:
        isiPutArgs = isiDescJson["PUT_args"]
        if "PUT_input_schema" in isiDescJson:
            itemInputSchema = isiDescJson["PUT_input_schema"]
        else:
            itemInputSchema = None
        operation = "update"
        swaggerPath["put"] = \
                CreateSwaggerOperation(
                        isiApiName, isiObjNameSpace, oneObjName, operation,
                        isiPutArgs, itemInputSchema, None, objDefs,
                        inputSchemaParamObjName)
        # add the item-id as a url path parameter
        putIdParam = itemIdParam.copy()
        putIdParam["description"] = isiPutArgs["description"]
        swaggerPath["put"]["parameters"].append(putIdParam)
        AddPathParams(swaggerPath["put"]["parameters"], extraPathParams)

    if "DELETE_args" in isiDescJson:
        isiDeleteArgs = isiDescJson["DELETE_args"]
        operation = "delete"
        swaggerPath["delete"] = \
                CreateSwaggerOperation(
                        isiApiName, isiObjNameSpace, oneObjName, operation,
                        isiDeleteArgs, None, None, objDefs)
        # add the item-id as a url path parameter
        delIdParam = itemIdParam.copy()
        delIdParam["description"] = isiDeleteArgs["description"]
        swaggerPath["delete"]["parameters"].append(delIdParam)
        AddPathParams(swaggerPath["delete"]["parameters"], extraPathParams)

    if "GET_args" in isiDescJson:
        isiGetArgs = isiDescJson["GET_args"]
        getRespSchema = isiDescJson["GET_output_schema"]
        operation = "get"
        # use the plural name so that the GET base end point's response
        # becomes subclass of this response object schema model
        swaggerPath["get"] = \
                CreateSwaggerOperation(
                        isiApiName, isiObjNameSpace, isiObjName, operation,
                        isiGetArgs, None, getRespSchema, objDefs)
        # hack to force the api function to be "get<SingleObj>"
        swaggerPath["get"]["operationId"] = operation + isiObjNameSpace + oneObjName
        # add the item-id as a url path parameter
        getIdParam = itemIdParam.copy()
        getIdParam["description"] = isiGetArgs["description"]
        swaggerPath["get"]["parameters"].append(getIdParam)
        AddPathParams(swaggerPath["get"]["parameters"], extraPathParams)

    if "POST_args" in isiDescJson:
        isiPostArgs = isiDescJson["POST_args"]
        postInputSchema = isiDescJson["POST_input_schema"]
        if "POST_output_schema" in isiDescJson:
            postRespSchema = isiDescJson["POST_output_schema"]
        else:
            postRespSchema = None
        operation = "create"
        swaggerPath["post"] = \
                CreateSwaggerOperation(
                        isiApiName, isiObjNameSpace, oneObjName, operation,
                        isiPostArgs, postInputSchema, postRespSchema, objDefs,
                        None, "CreateParams")
        AddPathParams(swaggerPath["post"]["parameters"], extraPathParams)

    return itemIdUrl, swaggerPath


def ParsePathParams(endPointPath):
    numericItemTypes = ["Lnn", "Zone", "Port", "Lin"]
    params = []
    for partialPath in endPointPath.split("/"):
        if len(partialPath) == 0 \
                or partialPath[0] != '<' or partialPath[-1] != '>':
            continue
        # remove all non alphanumeric characters
        paramName = re.sub('[^0-9a-zA-Z]+', '', partialPath.title())
        if paramName in numericItemTypes:
            paramType = "integer"
        else:
            paramType = "string"
        params.append((paramName, paramType))

    return params


def GetEndpointPaths(source_node_or_cluster, papi_port, baseUrl, auth,
        excludeEndPoints):
    """
    Gets the full list of PAPI URIs reported by source_node_or_cluster using
    the ?describe&list&json query arguments at the root level.
    Returns the URIs as a list of tuples where collection resources appear as
    (<collection-uri>, <single-item-uri>) and non-collection/static resources
    appear as (<uri>,None).
    """
    desc_list_parms = {"describe": "", "json": "", "list": ""}
    url = "https://" + source_node_or_cluster + ":" + papi_port + baseUrl
    resp = requests.get(url=url, params=desc_list_parms, auth=auth, verify=False)
    endPointListJson = json.loads(resp.text)

    baseEndPoints = {}
    endPointPaths = []
    epIndex = 0
    numEndPoints = len(endPointListJson["directory"])
    while epIndex < numEndPoints:
        curEndPoint = endPointListJson["directory"][epIndex]
        if curEndPoint[2] != '/':
            # skip floating point version numbers
            epIndex += 1
            continue
        #print "curEndPoint[" + str(epIndex) + "] = " + curEndPoint
        nextEpIndex = epIndex + 1
        while nextEpIndex < numEndPoints:
            nextEndPoint = endPointListJson["directory"][nextEpIndex]
            # strip off the version and compare to see if they are
            # the same.
            if nextEndPoint[2:] != curEndPoint[2:]:
                #if epIndex + 1 != nextEpIndex:
                #    print "Using " + curEndPoint
                break
            #print "Skipping " + curEndPoint
            curEndPoint = nextEndPoint
            epIndex = nextEpIndex
            nextEpIndex += 1

        if curEndPoint in excludeEndPoints:
            epIndex += 1
            continue

        if curEndPoint[-1] != '>':
            baseEndPoints[curEndPoint[2:]] = (curEndPoint, None)
        else:
            try:
                itemEndPoint = curEndPoint
                lastSlash = itemEndPoint.rfind('/')
                baseEndPointTuple = baseEndPoints[itemEndPoint[2:lastSlash]]
                baseEndPointTuple = (baseEndPointTuple[0], itemEndPoint)
                endPointPaths.append(baseEndPointTuple)
                del baseEndPoints[itemEndPoint[2:lastSlash]]
            except KeyError:
                # no base for this itemEndPoint
                endPointPaths.append((None, itemEndPoint))

        epIndex += 1

    # remaining base end points have no item end point
    for baseEndPointTuple in baseEndPoints.values():
        endPointPaths.append(baseEndPointTuple)

    def EndPointPathCompare(a, b):
        #print "Compare " + str(a) + " and " + str(b)
        lhs = a[0]
        if lhs is None:
            lhs = a[1]
        rhs = b[0]
        if rhs is None:
            rhs = b[1]
        if lhs.find(rhs) == 0 \
                or rhs.find(lhs) == 0:
            #print "Compare " + str(a) + " and " + str(b)
            #print "Use length"
            return len(rhs) - len(lhs)
        #print "Use alpha"
        return cmp(lhs, rhs)

    return sorted(endPointPaths, cmp=EndPointPathCompare)


def main():
    argparser = argparse.ArgumentParser(
            description="Builds the Swagger config from the "\
                    "PAPI end point descriptions.")
    argparser.add_argument('-i', '--input',
            dest="host", help="IP-address or hostname of the Isilon"\
            "cluster to use as input.",
            action="store")
    argparser.add_argument('-o', '--output',
            dest="outputFile", help="Path to the output file.",
            action="store")
    argparser.add_argument('-u', '--username', dest='username',
            help="The username to use for the cluster.",
            action='store', default=None)
    argparser.add_argument('-p', '--password', dest='password',
            help="The password to use for the cluster.",
            action='store', default=None)
    argparser.add_argument('-d', '--defs', dest='defsFile',
            help="Path to a file that contains pre-built Swagger data model "\
            "definitions.", action='store', default=None)
    argparser.add_argument('-t', '--test', dest='test',
            help="Test mode on.", action='store_true', default=False)

    args = argparser.parse_args()

    if args.username is None:
        args.username = raw_input("Please provide the username used to access "
                + args.host + " via PAPI: ")
    if args.password is None:
        args.password = getpass.getpass("Password: ")

    swaggerJson = {
        "swagger": "2.0",
        "info": {
          "version": "1.0.0",
          "title": "Isilon SDK",
          "description": "Isilon SDK - Swagger Open API Specification for OneFS API",
          "termsOfService": "http://www.emc.com",
          "contact": {
            "name": "Isilon SDK Team",
            "email": "sdk@isilon.com",
            "url": "http://www.emc.com"
          },
          "license": {
            "name": "MIT",
            "url": "http://github.com/gruntjs/grunt/blob/master/LICENSE-MIT"
          }
        },
        "schemes": [
          "https"
        ],
        "consumes": [
          "application/json"
        ],
        "produces": [
          "application/json"
        ],
        "securityDefinitions": {
          "basic_auth": {
            "type": "basic"
          }
        },
        "security": [{ "basic_auth": [] }],
        "paths": {},
        "definitions": {}
        }

    if args.defsFile:
        with open(args.defsFile, "r") as defFile:
            swaggerDefs = json.loads(defFile.read())
    else:
        swaggerDefs = {
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

    swaggerJson["definitions"] = swaggerDefs

    auth = HTTPBasicAuth(args.username, args.password)
    baseUrl = "/platform"
    papi_port = "8080"
    desc_parms = {"describe": "", "json": ""}

    if args.test is False:
        excludeEndPoints = [
                "/1/debug/echo/<TOKEN>", # returns null json
                "/1/filesystem/settings/character-encodings", # array with no items
                "/1/fsa/path", # returns plain text, not JSON
                "/1/license/eula", # returns plain text, not JSON
                "/1/test/proxy/args/req/sleep", # return null json
                "/1/test/proxy/args/req", # return null json
                "/1/test/proxy/args",
                "/1/test/proxy/uri/<LNN>",
                "/1/test/proxy/uri",
                "/2/versiontest/other",
                "/3/cluster/email/default-template",
                "/2/cluster/external-ips", # returns list not object
                "/3/fsa/results/<ID>/directories/<LIN>", # array with no items
                "/3/fsa/results/<ID>/directories" ] # array with no items
        endPointPaths = GetEndpointPaths(args.host, papi_port, baseUrl, auth,
                excludeEndPoints)
    else:
        endPointPaths = [
                ("/1/auth/groups/<GROUP>/members",
                 "/1/auth/groups/<GROUP>/members/<MEMBER>"),
                ("/1/auth/groups",
                 "/1/auth/groups/<GROUP>"),
                ("/1/auth/mapping/users/lookup", None),
                ("/3/auth/mapping/dump", None),
                (None, "/1/auth/access/<USER>"),
                ("/3/antivirus/settings", None),
                ("/3/antivirus/scan", None),
                (None, "/3/antivirus/quarantine/<PATH+>"),
                ("/3/antivirus/policies", "/3/antivirus/policies/<NAME>"),
                ("/1/protocols/nfs/exports", "/1/protocols/nfs/exports/<EID>"),
                ("/1/protocols/smb/shares", "/1/protocols/smb/shares/<SHARE>"),
                ("/1/storagepool/unprovisioned", None),
                (None, "/3/hardware/tape/<name*>"),
                ("/1/auth/mapping/identities",
                 "/1/auth/mapping/identities/<SOURCE>"),
                ("/3/statistics/summary/client", None),
                ("/1/storagepool/tiers",
                 "/1/storagepool/tiers/<TID>"),
                ("/1/zones-summary",
                 "/1/zones-summary/<ZONE>")]

    successCount = 0
    failCount = 0
    objectDefs = swaggerJson["definitions"]
    for endPointTuple in endPointPaths:
        baseEndPointPath = endPointTuple[0]
        itemEndPointPath = endPointTuple[1]
        if baseEndPointPath is None:
            tmpBaseEndPointPath = \
                    ToSwaggerEndPoint(os.path.dirname(itemEndPointPath))
            swaggerPath = baseUrl + tmpBaseEndPointPath
            apiName, objNameSpace, objName = \
                    EndPointPathToApiObjName(tmpBaseEndPointPath)
        else:
            apiName, objNameSpace, objName = \
                    EndPointPathToApiObjName(baseEndPointPath)
            swaggerPath = baseUrl + ToSwaggerEndPoint(baseEndPointPath)

        if itemEndPointPath is not None:
            print >> sys.stderr, "Processing " + itemEndPointPath
            # next do the item PUT (i.e. update), DELETE, and GET because the GET seems
            # to be a limited version of the base path GET so the subclassing works
            # correct when done in this order
            url = "https://" + args.host + ":" + papi_port + baseUrl \
                    + itemEndPointPath
            resp = requests.get(url=url, params=desc_parms, auth=auth, verify=False)

            itemRespJson = json.loads(resp.text)

            singularObjPostfix, itemInputType = \
                    ParsePathParams(os.path.basename(itemEndPointPath))[0]
            extraPathParams = \
                    ParsePathParams(os.path.dirname(itemEndPointPath))
            try:
            #if True:
                itemPathUrl, itemPath = \
                        IsiItemEndPointDescToSwaggerPath(
                                apiName, objNameSpace, objName, itemRespJson,
                                singularObjPostfix, itemInputType,
                                extraPathParams, objectDefs)
                swaggerJson["paths"][swaggerPath + itemPathUrl] = itemPath

                if "HEAD_args" in itemRespJson:
                    print >> sys.stderr, "WARNING: HEAD_args in: " + itemEndPointPath

                successCount += 1
            except Exception as e:
            #    print >> sys.stderr, "Caught exception processing: " + itemEndPointPath
                failCount += 1

        if baseEndPointPath is not None:
            print >> sys.stderr, "Processing " + baseEndPointPath
            url = "https://" + args.host + ":" + papi_port + baseUrl \
                    + baseEndPointPath
            resp = requests.get(url=url, params=desc_parms, auth=auth, verify=False)
            baseRespJson = json.loads(resp.text)
            basePathParams = ParsePathParams(baseEndPointPath)
            basePath = {}
            # start with base path POST because it defines the base creation object
            # model
            try:
            #if True:
                if "POST_args" in baseRespJson:
                    basePath = IsiPostBaseEndPointDescToSwaggerPath(
                                    apiName, objNameSpace, objName, baseRespJson,
                                    basePathParams, objectDefs)

                if "GET_args" in baseRespJson:
                    getBasePath = IsiGetBaseEndPointDescToSwaggerPath(
                                    apiName, objNameSpace, objName, baseRespJson,
                                    basePathParams, objectDefs)
                    basePath.update(getBasePath)

                if "PUT_args" in baseRespJson:
                    putBasePath = IsiPutBaseEndPointDescToSwaggerPath(
                                    apiName, objNameSpace, objName, baseRespJson,
                                    basePathParams, objectDefs)
                    basePath.update(putBasePath)

                if "DELETE_args" in baseRespJson:
                    delBasePath = IsiDeleteBaseEndPointDescToSwaggerPath(
                                    apiName, objNameSpace, objName, baseRespJson,
                                    basePathParams, objectDefs)
                    basePath.update(delBasePath)

                if len(basePath) > 0:
                    swaggerJson["paths"][swaggerPath] = basePath

                if "HEAD_args" in baseRespJson:
                    print >> sys.stderr, "WARNING: HEAD_args in: " + baseEndPointPath
                successCount += 1
            except Exception as e:
            #    print >> sys.stderr, "Caught exception processing: " + baseEndPointPath
                failCount += 1

    print >> sys.stderr, "End points successfully processed: " + str(successCount) \
            + ", failed to process: " + str(failCount) \
            + ", excluded: " + str(len(excludeEndPoints)) + "."

    with open(args.outputFile, "w") as outputFile:
        outputFile.write(json.dumps(swaggerJson,
            sort_keys=True, indent=4, separators=(',', ': ')))


if __name__ == "__main__":
    main()
