#!/usr/bin/python
"""
Basic unit/smoke tests for the create_swagger_config generator.
Does not assume access to any cluster for the ability to actually generate
a swagger config.
"""

import unittest

class TestCreateSwaggerConfig(unittest.TestCase):

    def test_ToSwaggerEndPoint(self):
        TEST_URIS = [
            "/an/<end>/<point>/with/<params>",
            "/no/params/in/this/one"
        ]
        EXPECTED_RESULTS = [
            "/an/{End}/{Point}/with/{Params}",
            "/no/params/in/this/one"
        ]
        # It replaces <papi-style> URI param markers with {Swagger-style}.
        for i in range(len(TEST_URIS)):
            self.assertEqual(
                csc.ToSwaggerEndPoint(TEST_URIS[i]),
                EXPECTED_RESULTS[i])

    def test_AddPathParams(self):
        TEST_PARAMS = [
            ('Someparametername', 'string'),
            ('Anotherparam', 'integer')]
        EXPECTED_RESULTS = [
            {
                'name': TEST_PARAMS[0][0],
                'in': 'path',
                'required': True,
                'type': TEST_PARAMS[0][1]
            },
            {
                'name': TEST_PARAMS[1][0],
                'in': 'path',
                'required': True,
                'type': TEST_PARAMS[1][1]
            }
        ]
        # It appends a param object based on specified param name and type.
        swaggerParams = []
        csc.AddPathParams(swaggerParams, [TEST_PARAMS[0]])
        self.assertTrue(EXPECTED_RESULTS[0] in swaggerParams)
        csc.AddPathParams(swaggerParams, [TEST_PARAMS[1]])
        self.assertTrue(EXPECTED_RESULTS[1] in swaggerParams)

    def test_ParsePathParams(self):
        PATHS = [
            '/this/uri/has/a/<parameter>',
            '/this/uri/has/a/<lnn>',
            '/this/<uri>/has/<lnn>/and/<multiple>/parameters',
            '/this/one/doesnt/have/parameters/like/that'
        ]
        # It correctly parses string parameters from a URI.
        self.assertEqual(
            csc.ParsePathParams(PATHS[0]),
            [('Parameter', 'string')])
        # It correctly parses integer parameters from a URI.
        self.assertEqual(
            csc.ParsePathParams(PATHS[1]),
            [('Lnn', 'integer')])
        # It correctly parses multiple parameters from a URI.
        self.assertEqual(
            csc.ParsePathParams(PATHS[2]),
            [('Uri', 'string'), ('Lnn', 'integer'), ('Multiple', 'string')])
        # It returns an empty list given a URI with no params.
        self.assertEqual(
            csc.ParsePathParams(PATHS[3]),
            [])

if __name__ == '__main__':
    if __package__ is None:
        import sys
        from os import path
        # Append swagger-config-generator root directory. 
        sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
        from components import create_swagger_config as csc
        from components import papi_swagger_obj_defs_builder as odb
        unittest.main()
    else:
        from ..components import create_swagger_config as csc
        from ..components import papi_swagger_obj_defs_builder as odb
        unittest.main()
