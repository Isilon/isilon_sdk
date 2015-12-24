import json
import requests
from requests.auth import HTTPBasicAuth
import sys


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


def IsiSchemaToSwaggerObjectDefs(isiObjName, isiSchema, objDefs):
    # converts isiSchema to a single schema with "#ref" for sub-objects
    # which is what Swagger expects. Adds the sub-objects to the objDefs
    # list.
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
            # so use the first type (i guess)
            firstType = prop["type"][0]
            # sometimes the types are base types and sometimes they
            # are sub objects
            if type(firstType) == dict:
                outerPropDesc = prop["description"]
                prop = isiSchema["properties"][propName] = firstType
                prop["description"] = outerPropDesc \
                        + " " + prop["description"] \
                        if "description" in prop else outerPropDesc
            else:
                prop["type"] = firstType

        if prop["type"] == "object":
            subObjName = isiObjName + "_" + propName
            objRef = IsiSchemaToSwaggerObjectDefs(subObjName, prop, objDefs)
            isiSchema["properties"][propName] = {"$ref" : objRef}
        elif prop["type"] == "array" and prop["items"]["type"] == "object":
            if isiObjName[-1] == 's':
                # if container object ends with 's' then trim off the 's'
                # to (hopefully) create the singular version
                itemsObjName = isiObjName[:-1]
            else:
                itemsObjName = isiObjName + "Item"
            objRef = IsiSchemaToSwaggerObjectDefs(itemsObjName, prop["items"], objDefs)
            isiSchema["properties"][propName]["items"] = {"$ref" : objRef}
        if "required" in prop and prop["required"] == True:
            del isiSchema["properties"][propName]["required"]
            requiredProps.append(propName)

    if len(requiredProps) > 0:
        isiSchema["required"] = requiredProps

    return FindOrAddObjDef(objDefs, isiSchema, isiObjName)


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
    del names[0]
    isiObjName = ""
    for name in names:
        isiObjName += name.title()
    return isiApiName, isiObjName


def CreateSwaggerOperation(
        isiApiName, isiObjName, operation,
        isiInputArgs, isiInputSchema, isiRespSchema, objDefs):
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
    swaggerOperation["operationId"] = operation+isiObjName

    isiRespObjName = isiObjName

    if isiInputSchema is not None:
        objRef = IsiSchemaToSwaggerObjectDefs(isiObjName, isiInputSchema, objDefs)
        inputSchemaParam = {}
        inputSchemaParam["in"] = "body"
        inputSchemaParam["name"] = isiObjName
        inputSchemaParam["required"] = True
        inputSchemaParam["schema"] = { "$ref": objRef }
        swaggerParams.append(inputSchemaParam)
        # just use the operation for the response because it seems like all the
        # responses to POST have the same schema
        isiRespObjName = operation[0].upper() + operation[1:] + "Response"

    swaggerOperation["parameters"] = swaggerParams

    # create responses
    swaggerResponses = {}
    if isiRespSchema is not None:
        objRef = IsiSchemaToSwaggerObjectDefs(isiRespObjName, isiRespSchema, objDefs)
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


def IsiPostBaseEndPointDescToSwaggerPath(isiApiName, isiObjName, isiDescJson, objDefs):
    swaggerPath = {}
    isiPostArgs = isiDescJson["POST_args"]
    if isiObjName[-1] == 's':
        # create the singular version
        oneObjName = isiObjName[:-1]
    else:
        # prepend an "A" to make it singular (i guess)
        oneObjName = "A"+isiObjName

    postInputSchema = isiDescJson["POST_input_schema"]
    postRespSchema = isiDescJson["POST_output_schema"]
    operation = "create"
    swaggerPath["post"] = \
            CreateSwaggerOperation(
                    isiApiName, oneObjName, operation,
                    isiPostArgs, postInputSchema, postRespSchema, objDefs)

    return swaggerPath


def IsiGetBaseEndPointDescToSwaggerPath(isiApiName, isiObjName, isiDescJson, objDefs):
    swaggerPath = {}

    if "GET_args" in isiDescJson:
        isiGetArgs = isiDescJson["GET_args"]
        getRespSchema = isiDescJson["GET_output_schema"]
        operation = "list"
        swaggerPath["get"] = \
                CreateSwaggerOperation(
                        isiApiName, isiObjName, operation,
                        isiGetArgs, None, getRespSchema, objDefs)

    return swaggerPath


def IsiItemEndPointDescToSwaggerPath(
        isiApiName, isiObjName, isiDescJson, itemInputSchema, objDefs):
    swaggerPath = {}
    # first deal with POST and PUT in order to create the objects that are used
    # in the GET
    if isiObjName[-1] == 's':
        # create the singular version
        oneObjName = isiObjName[:-1]
    else:
        # prepend an "A" to make it singular (i guess)
        oneObjName = "A"+isiObjName
    itemId = oneObjName + "Id"
    itemIdUrl = "/{" + itemId + "}"
    itemIdParam = {}
    itemIdParam["name"] = itemId
    itemIdParam["in"] = "path"
    itemIdParam["required"] = True
    itemIdParam["type"] = "integer"

    if "PUT_args" in isiDescJson:
        isiPutArgs = isiDescJson["PUT_args"]
        operation = "update"
        swaggerPath["put"] = \
                CreateSwaggerOperation(
                        isiApiName, oneObjName, operation,
                        isiPutArgs, itemInputSchema, None, objDefs)
        # add the item-id as a url path parameter
        putIdParam = itemIdParam.copy()
        putIdParam["description"] = isiPutArgs["description"]
        swaggerPath["put"]["parameters"].append(putIdParam)

    if "DELETE_args" in isiDescJson:
        isiDeleteArgs = isiDescJson["DELETE_args"]
        operation = "delete"
        swaggerPath["delete"] = \
                CreateSwaggerOperation(
                        isiApiName, oneObjName, operation,
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
                        isiApiName, isiObjName, operation,
                        isiGetArgs, None, getRespSchema, objDefs)
        # hack to force the api function to be "get<SingleObj>"
        swaggerPath["get"]["operationId"] = operation+oneObjName
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
endPointPath = "/1/protocols/nfs/exports"
url = "https://137.69.154.252:8080" + baseUrl + endPointPath
params = {"describe": "", "json": ""}
resp = requests.get(url=url, params=params, auth=auth, verify=False)

if resp.status_code == 200:
    respJson = json.loads(resp.text)
    apiName, objName = EndPointPathToApiObjName(endPointPath)
    objectDefs = {}
    swaggerPath = baseUrl + endPointPath
    basePath = {}
    # start with base path POST because it defines the base creation object
    # model
    if "POST_args" in respJson:
        basePath = IsiPostBaseEndPointDescToSwaggerPath(apiName, objName, respJson, objectDefs)
    # next do the item PUT (i.e. update), DELETE, and GET because the GET seems
    # to be a limited version of the base path GET so the subclassing works
    # correct when done in this order
    if "POST_input_schema" in respJson:
        itemInputSchema = respJson["POST_input_schema"]
        endPointPath += "/<EID>"
        url = "https://137.69.154.252:8080" + baseUrl + endPointPath
        resp = requests.get(url=url, params=params, auth=auth, verify=False)
        itemRespJson = json.loads(resp.text)
        itemPathUrl, itemPath = \
                IsiItemEndPointDescToSwaggerPath(
                        apiName, objName, itemRespJson,
                        itemInputSchema, objectDefs)
        swaggerJson["paths"][swaggerPath + itemPathUrl] = itemPath
    # lastly do the base path GET, which if there is an item path GET then most
    # likely the base path GET will define a subclass of the item path GET
    if "GET_args" in respJson:
        getBasePath = IsiGetBaseEndPointDescToSwaggerPath(apiName, objName, respJson, objectDefs)
        basePath.update(getBasePath)
    if len(basePath) > 0:
        swaggerJson["paths"][swaggerPath] = basePath
    swaggerJson["definitions"].update(objectDefs)

    print json.dumps(swaggerJson,
            sort_keys=True, indent=4, separators=(',', ': '))
