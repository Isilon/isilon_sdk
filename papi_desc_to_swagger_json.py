#!/usr/bin/python
import json
import os
import re
import requests
from requests.auth import HTTPBasicAuth
import sys

requests.packages.urllib3.disable_warnings()

k_swaggerParamIsiPropCommonFields = [
    "description", "required", "type", "default", "maximum", "minimum", "enum"]

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
                print >> sys.stderr, "WARNING:" + fieldName + " not defined for Swagger."
                continue
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
            oneObjName = objName[:-3].title().replace('_', '') + "y"
        else:
            oneObjName = objName[:-1].title().replace('_', '')
    else:
        oneObjName = objName.title().replace('_', '') + postFix
        if postFixUsed is not None:
            postFixUsed.flag = True

    return oneObjName


def IsiSchemaToSwaggerObjectDefs(
        isiObjNameSpace, isiObjName, isiSchema, objDefs):
    # converts isiSchema to a single schema with "#ref" for sub-objects
    # which is what Swagger expects. Adds the sub-objects to the objDefs
    # list.
    if type(isiSchema["type"]) == list:
        for schemaListItem in isiSchema["type"]:
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

    requiredProps = []
    for propName in isiSchema["properties"]:
        prop = isiSchema["properties"][propName]
        if "type" not in prop:
            continue # must be a $ref
        if type(prop["type"]) == list:
            # swagger doesn't like lists for types
            # so use the first type that is not "null"
            multipleTypes = prop["type"]
            # delete it so that we throw an exception if none of types
            # are non-"null"
            del prop["type"]
            for oneType in multipleTypes:
                # sometimes the types are base types and sometimes they
                # are sub objects
                if type(oneType) == dict:
                    outerPropDesc = prop["description"]
                    prop = isiSchema["properties"][propName] = oneType
                    prop["description"] = outerPropDesc \
                            + " " + prop["description"] \
                            if "description" in prop else outerPropDesc
                    break
                elif oneType != "null":
                    prop["type"] = oneType
                    break

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
                        subObjNameSpace, subObjName, prop, objDefs)
            isiSchema["properties"][propName] = \
                    {"description" : propDescription, "$ref" : objRef}
        elif prop["type"] == "array":
            # code below is work around for bug in /auth/access/<USER> end point
            if "items" not in prop and "item" in prop:
                prop["items"] = prop["item"]
                del prop["item"]

            if "type" in prop["items"] and prop["items"]["type"] == "object":
                itemsObjName = PluralObjNameToSingular(propName, postFix="Item")
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
                            prop["items"], objDefs)
                isiSchema["properties"][propName]["items"] = \
                        {"description" : propDescription, "$ref" : objRef}
            elif "type" not in prop["items"] and "$ref" not in prop["items"]:
                raise RuntimeError("Array with no type or $ref: " + str(prop))

        if "required" in prop and prop["required"] == True:
            if "required" in isiSchema["properties"][propName]:
                del isiSchema["properties"][propName]["required"]
            requiredProps.append(propName)

    # attache required props
    if len(requiredProps) > 0:
        isiSchema["required"] = requiredProps

    return FindOrAddObjDef(objDefs, isiSchema, isiObjNameSpace + isiObjName)


def FindOrAddObjDef(objDefs, newObjDef, newObjName):
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
        # TODO need a better way to name subclasses
        newObjName += "Extended"
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
    isiApiName = names[0].title()
    if len(names) == 2:
        isiObjNameSpace = isiApiName
    else:
        isiObjNameSpace = names[1].title()
        del names[0]
    del names[0]
    if len(names) == 0:
        isiObjName = isiObjNameSpace
    else:
        isiObjName = ""
        for name in names:
            isiObjName += name.title()
    return isiApiName, isiObjNameSpace, isiObjName


def CreateSwaggerOperation(
        isiApiName, isiObjNameSpace, isiObjName, operation,
        isiInputArgs, isiInputSchema, isiRespSchema, objDefs,
        inputSchemaParamObjName=None):
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
                    isiInputSchema, objDefs)
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
                    isiRespObjNameSpace, isiRespObjName, isiRespSchema, objDefs)
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


def IsiPostBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, objDefs):
    swaggerPath = {}
    isiPostArgs = isiDescJson["POST_args"]
    oneObjName = PluralObjNameToSingular(isiObjName, postFix="Item")

    postInputSchema = isiDescJson["POST_input_schema"]
    postRespSchema = isiDescJson["POST_output_schema"]
    operation = "create"
    swaggerPath["post"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, oneObjName, operation,
                    isiPostArgs, postInputSchema, postRespSchema, objDefs)

    return swaggerPath


def IsiPutBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, objDefs):
    swaggerPath = {}
    inputArgs = isiDescJson["PUT_args"]

    inputSchema = isiDescJson["PUT_input_schema"]
    operation = "update"
    swaggerPath["put"] = \
            CreateSwaggerOperation(
                    isiApiName, isiObjNameSpace, isiObjName, operation,
                    inputArgs, inputSchema, None, objDefs)

    return swaggerPath


def IsiGetBaseEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName, isiDescJson, objDefs):
    swaggerPath = {}

    if "GET_args" in isiDescJson:
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

    return swaggerPath


def IsiItemEndPointDescToSwaggerPath(
        isiApiName, isiObjNameSpace, isiObjName,
        isiDescJson, itemInputSchema, objDefs,
        singleObjPostFix, itemInputType):
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

    return itemIdUrl, swaggerPath


swaggerJson = {
    "swagger": "2.0",
    "info": {
      "version": "1.0.0",
      "title": "Isilon PAPI",
      "description": "Isilon Platform API.",
      "termsOfService": "http://emc.com",
      "contact": {
        "name": "Isilon PAPI Team",
        "email": "papi@isilon.com",
        "url": "http://emc.com"
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
    "definitions": {
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
      }
    }
}

auth = HTTPBasicAuth("root", "a")
baseUrl = "/platform"
desc_parms = {"describe": "", "json": ""}

numericItemTypes = ["Lnn", "Zone", "Port", "Lin"]
endPointPaths = [
    (None, "/1/auth/access/<USER>"),
    ("/3/antivirus/settings", None),
    ("/3/antivirus/scan", None),
    (None, "/3/antivirus/quarantine/<PATH+>"),
    ("/3/antivirus/policies", "/3/antivirus/policies/<NAME>"),
    ("/1/protocols/nfs/exports", "/1/protocols/nfs/exports/<EID>"),
    ("/1/protocols/smb/shares", "/1/protocols/smb/shares/<SHARE>")]

for endPointTuple in endPointPaths:
    itemInputSchema = None
    baseRespJson = None
    apiName = None
    objNameSpace = None
    objName = None
    swaggerPath = None
    objectDefs = {}

    baseEndPointPath = endPointTuple[0]
    if baseEndPointPath is not None:
        url = "https://137.69.154.252:8080" + baseUrl + baseEndPointPath
        resp = requests.get(url=url, params=desc_parms, auth=auth, verify=False)
        baseRespJson = json.loads(resp.text)
        apiName, objNameSpace, objName = EndPointPathToApiObjName(baseEndPointPath)
        swaggerPath = baseUrl + baseEndPointPath
        basePath = {}
        # start with base path POST because it defines the base creation object
        # model
        if "POST_args" in baseRespJson:
            basePath = IsiPostBaseEndPointDescToSwaggerPath(
                            apiName, objNameSpace, objName, baseRespJson, objectDefs)
        if "POST_input_schema" in baseRespJson:
            itemInputSchema = baseRespJson["POST_input_schema"]

    itemEndPointPath = endPointTuple[1]
    if itemEndPointPath is not None:
        if baseEndPointPath is None:
            tmpBaseEndPointPath = os.path.dirname(itemEndPointPath)
            swaggerPath = baseUrl + tmpBaseEndPointPath
            apiName, objNameSpace, objName = \
                    EndPointPathToApiObjName(tmpBaseEndPointPath)
        # next do the item PUT (i.e. update), DELETE, and GET because the GET seems
        # to be a limited version of the base path GET so the subclassing works
        # correct when done in this order
        url = "https://137.69.154.252:8080" + baseUrl + itemEndPointPath
        resp = requests.get(url=url, params=desc_parms, auth=auth, verify=False)
        itemRespJson = json.loads(resp.text)
        if itemInputSchema is None and "PUT_input_schema" in itemRespJson:
            itemInputSchema = itemRespJson["PUT_input_schema"]

        singularObjPostfix = re.sub('[^0-9a-zA-Z]+', '',
                                   os.path.basename(itemEndPointPath)).title()
        if singularObjPostfix in numericItemTypes:
            itemInputType = "integer"
        else:
            itemInputType = "string"
        itemPathUrl, itemPath = \
                IsiItemEndPointDescToSwaggerPath(
                        apiName, objNameSpace, objName, itemRespJson,
                        itemInputSchema, objectDefs, singularObjPostfix,
                        itemInputType)
        swaggerJson["paths"][swaggerPath + itemPathUrl] = itemPath
    # lastly do the base path GET, which if there is an item path GET then most
    # likely the base path GET will define a subclass of the item path GET
    if baseEndPointPath is not None:
        if "GET_args" in baseRespJson:
            getBasePath = IsiGetBaseEndPointDescToSwaggerPath(
                            apiName, objNameSpace, objName, baseRespJson, objectDefs)
            basePath.update(getBasePath)

        if "PUT_args" in baseRespJson:
            putBasePath = IsiPutBaseEndPointDescToSwaggerPath(
                            apiName, objNameSpace, objName, baseRespJson, objectDefs)
            basePath.update(putBasePath)


        if len(basePath) > 0:
            swaggerJson["paths"][swaggerPath] = basePath

    if len(objectDefs) > 0:
        swaggerJson["definitions"].update(objectDefs)

print json.dumps(swaggerJson,
        sort_keys=True, indent=4, separators=(',', ': '))
