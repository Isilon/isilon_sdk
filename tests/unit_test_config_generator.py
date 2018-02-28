#!/usr/bin/python
"""
Basic unit/smoke tests for the create_swagger_config generator.
Does not assume access to any cluster for the ability to actually generate
a swagger config.
"""

import unittest

class TestCreateSwaggerConfig(unittest.TestCase):

    def test_to_swagger_end_point(self):
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
                csc.to_swagger_end_point(TEST_URIS[i]),
                EXPECTED_RESULTS[i])

    def test_add_path_params(self):
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
        csc.add_path_params(swaggerParams, [TEST_PARAMS[0]])
        self.assertTrue(EXPECTED_RESULTS[0] in swaggerParams)
        csc.add_path_params(swaggerParams, [TEST_PARAMS[1]])
        self.assertTrue(EXPECTED_RESULTS[1] in swaggerParams)

    def test_parse_path_params(self):
        PATHS = [
            '/this/uri/has/a/<parameter>',
            '/this/uri/has/a/<lnn>',
            '/this/<uri>/has/<lnn>/and/<multiple>/parameters',
            '/this/one/doesnt/have/parameters/like/that'
        ]
        # It correctly parses string parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(PATHS[0]),
            [('Parameter', 'string')])
        # It correctly parses integer parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(PATHS[1]),
            [('Lnn', 'integer')])
        # It correctly parses multiple parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(PATHS[2]),
            [('Uri', 'string'), ('Lnn', 'integer'), ('Multiple', 'string')])
        # It returns an empty list given a URI with no params.
        self.assertEqual(csc.parse_path_params(PATHS[3]), [])

    def test_isi_props_to_swagger_params(self):
        """Pattern is wrapped with forward slashes."""
        isi_props = {
            'licenses_to_include': {
                'description': 'Licenses to include in activation file.',
                'maxLength': 2500,
                'minLength': 1,
                'pattern': '.+',
                'type': 'string'
            }
        }
        actual = csc.isi_props_to_swagger_params(isi_props, 'query')

        expected = [{
            'description': 'Licenses to include in activation file.',
            'pattern': '/.+/',
            'in': 'query',
            'minLength': 1,
            'maxLength': 2500,
            'type': 'string',
            'name': 'licenses_to_include'
        }]
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    if __package__ is None:
        import sys
        from os import path
        # Append swagger-config-generator root directory.
        sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
        from components import create_swagger_config as csc
        unittest.main()
    else:
        from ..components import create_swagger_config as csc
        unittest.main()
