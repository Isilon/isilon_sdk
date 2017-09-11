# coding: utf-8

"""
Copyright 2016 SmartBear Software

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Credit: this file (rest.py) is modified based on rest.py in Dropbox Python SDK:
https://www.dropbox.com/developers/core/sdks/python
"""
from __future__ import absolute_import

import sys
import io
import json
import ssl
import certifi
import logging
import re

# python 2 and python 3 compatibility library
from six import iteritems

from .configuration import Configuration

try:
    import urllib3
except ImportError:
    raise ImportError('Swagger python client requires urllib3.')

try:
    import isi.rest
except ImportError:
	# This isn't really an error because the library is only used when running
	# on-cluster.
	pass

try:
    # for python3
    from urllib.parse import urlencode
except ImportError:
    # for python2
    from urllib import urlencode
try:
    # for python3
    from urllib.parse import unquote
except ImportError:
    # for python2
    from urllib import unquote


logger = logging.getLogger(__name__)


class RESTResponse(io.IOBase):

    def __init__(self, resp):
        self.urllib3_response = resp
        self.status = resp.status
        self.reason = resp.reason
        self.data = resp.data

    def getheaders(self):
        """
        Returns a dictionary of the response headers.
        """
        return self.urllib3_response.getheaders()

    def getheader(self, name, default=None):
        """
        Returns a given response header.
        """
        return self.urllib3_response.getheader(name, default)


class RESTClientObject(object):

    def __init__(self, pools_size=4):
        # urllib3.PoolManager will pass all kw parameters to connectionpool
        # https://github.com/shazow/urllib3/blob/f9409436f83aeb79fbaf090181cd81b784f1b8ce/urllib3/poolmanager.py#L75
        # https://github.com/shazow/urllib3/blob/f9409436f83aeb79fbaf090181cd81b784f1b8ce/urllib3/connectionpool.py#L680
        # ca_certs vs cert_file vs key_file
        # http://stackoverflow.com/a/23957365/2985775

        # cert_reqs
        if Configuration().verify_ssl:
            cert_reqs = ssl.CERT_REQUIRED
        else:
            cert_reqs = ssl.CERT_NONE

        # ca_certs
        if Configuration().ssl_ca_cert:
            ca_certs = Configuration().ssl_ca_cert
        else:
            # if not set certificate file, use Mozilla's root certificates.
            ca_certs = certifi.where()

        # cert_file
        cert_file = Configuration().cert_file

        # key file
        key_file = Configuration().key_file

        # https pool manager
        self.pool_manager = urllib3.PoolManager(
            num_pools=pools_size,
            cert_reqs=cert_reqs,
            ca_certs=ca_certs,
            cert_file=cert_file,
            key_file=key_file
        )

    def request(self, method, url, query_params=None, headers=None,
                body=None, post_params=None):
        """
        :param method: http request method
        :param url: http request url
        :param query_params: query parameters in the url
        :param headers: http request headers
        :param body: request json body, for `application/json`
        :param post_params: request post parameters,
                            `application/x-www-form-urlencode`
                            and `multipart/form-data`
        """
        method = method.upper()
        assert method in ['GET', 'HEAD', 'DELETE', 'POST', 'PUT', 'PATCH', 'OPTIONS']

        if post_params and body:
            raise ValueError(
                "body parameter cannot be used with post_params parameter."
            )

        post_params = post_params or {}
        headers = headers or {}

        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        try:
            # For `POST`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`
            if method in ['POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE']:
                if headers['Content-Type'] == 'application/json':
                    r = self._submit_requests(method,
                                              url,
                                              query_params=query_params,
                                              headers=headers,
                                              body=json.dumps(body))
                if headers['Content-Type'] == 'application/x-www-form-urlencoded':
                    r = self._submit_requests(method,
                                              url,
                                              query_params=query_params,
                                              headers=headers,
                                              post_params=post_params,
                                              encode_multipart=False)
                if headers['Content-Type'] == 'multipart/form-data':
                    # must del headers['Content-Type'], or the correct Content-Type
                    # which generated by urllib3 will be overwritten.
                    del headers['Content-Type']
                    r = self._submit_requests(method,
                                              url,
                                              query_params=query_params,
                                              headers=headers,
                                              post_params=post_params,
                                              encode_multipart=True)
            # For `GET`, `HEAD`
            else:
                r = self._submit_requests(method,
                                          url,
                                          query_params=query_params,
                                          headers=headers)
        except (urllib3.exceptions.SSLError, urllib3.exceptions.HTTPError) as e:
            msg = "{0}\n{1}".format(type(e).__name__, str(e))
            raise ApiException(status=0, reason=msg)

        r = RESTResponse(r)

        # In the python 3, the response.data is bytes.
        # we need to decode it to string.
        if sys.version_info > (3,):
            r.data = r.data.decode('utf8')

        # log response body
        logger.debug("response body: %s" % r.data)

        if r.status not in range(200, 206):
            raise ApiException(http_resp=r)

        return r


    def _submit_requests(self, method, url, query_params=None, headers=None,
                         body=None, post_params=None, encode_multipart=None):
        if url.startswith('papi://PAPI_LOCAL_HOST'):
            # operating on-cluster.  use isi.rest with papi.sock instead of urllib3
            # so we can avoid re-authenticating.

            if 'Authorization' in headers:
                del headers['Authorization']

            if post_params is not None:
                # post parameters should be passed in the message body
                body = post_params
            elif body is None:
                # both body and post_params are none, pass in an empty body
                body = '{}'

            # the body field must be a string
            if not isinstance(body, basestring):
                body = json.dumps(body)

            url_parts = url.partition('/platform/')[2].split('/')
            # isi.rest will re-encode the url so decode each part.  this is stupid
            # but needed unless someone knows a way to get send_rest_request() to
            # not re-encode the url parts.
            for i in range(0, len(url_parts)):
                url_parts[i] = unquote(url_parts[i])

            response = isi.rest.send_rest_request(isi.rest.PAPI_SOCKET_PATH,
                                                  method=method,
                                                  uri=url_parts,
                                                  query_args=query_params,
                                                  headers=headers,
                                                  body=body,
                                                  timeout=120)

            # we only use the headers, status, reason and body of a urllib3
            # response object.  the response from isi.rest.set_rest_request is:
            # [status, headers subset, body]
            reason = 'Response code: ' + str(response[0])
            if 'status' in response[1]:
                reason = response[1]['status']
                # the contents of the status field are: 'XXX reason_string'
                reason = reason[4:]
            r = urllib3.HTTPResponse(headers=response[1],
                                     status=response[0],
                                     reason=reason,
                                     body=response[2])
        else:
            if method in ['POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE']:
                if query_params:
                    url += '?' + urlencode(query_params)
            elif method in ['GET', 'HEAD']:
                post_params = query_params
            if encode_multipart is not None:
                r = self.pool_manager.request(method,
                                              url,
                                              body=body,
                                              fields=post_params,
                                              headers=headers,
                                              encode_multipart=encode_multipart)
            else:
                r = self.pool_manager.request(method,
                                              url,
                                              body=body,
                                              fields=post_params,
                                              headers=headers)
        return r



    def GET(self, url, headers=None, query_params=None):
        return self.request("GET", url,
                            headers=headers,
                            query_params=query_params)

    def HEAD(self, url, headers=None, query_params=None):
        return self.request("HEAD", url,
                            headers=headers,
                            query_params=query_params)

    def OPTIONS(self, url, headers=None, query_params=None, post_params=None, body=None):
        return self.request("OPTIONS", url,
                            headers=headers,
                            query_params=query_params,
                            post_params=post_params,
                            body=body)

    def DELETE(self, url, headers=None, query_params=None, body=None):
        return self.request("DELETE", url,
                            headers=headers,
                            query_params=query_params,
                            body=body)

    def POST(self, url, headers=None, query_params=None, post_params=None, body=None):
        return self.request("POST", url,
                            headers=headers,
                            query_params=query_params,
                            post_params=post_params,
                            body=body)

    def PUT(self, url, headers=None, query_params=None, post_params=None, body=None):
        return self.request("PUT", url,
                            headers=headers,
                            query_params=query_params,
                            post_params=post_params,
                            body=body)

    def PATCH(self, url, headers=None, query_params=None, post_params=None, body=None):
        return self.request("PATCH", url,
                            headers=headers,
                            query_params=query_params,
                            post_params=post_params,
                            body=body)


class ApiException(Exception):

    def __init__(self, status=None, reason=None, http_resp=None):
        if http_resp:
            self.status = http_resp.status
            self.reason = http_resp.reason
            self.body = http_resp.data
            self.headers = http_resp.getheaders()
        else:
            self.status = status
            self.reason = reason
            self.body = None
            self.headers = None

    def __str__(self):
        """
        Custom error messages for exception
        """
        error_message = "({0})\n"\
                        "Reason: {1}\n".format(self.status, self.reason)
        if self.headers:
            error_message += "HTTP response headers: {0}\n".format(self.headers)

        if self.body:
            error_message += "HTTP response body: {0}\n".format(self.body)

        return error_message
