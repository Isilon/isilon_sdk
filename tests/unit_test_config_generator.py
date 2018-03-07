#!/usr/bin/python
"""
Basic unit/smoke tests for the create_swagger_config generator.
Does not assume access to any cluster for the ability to actually generate
a swagger config.
"""
import copy
import unittest

class TestCreateSwaggerConfig(unittest.TestCase):
    """Test class for components/create_swagger_config.py."""

    def test_to_swagger_end_point(self):
        """Convert PAPI endpoints to Swagger endpoints."""
        test_uris = [
            "/an/<end>/<point>/with/<params>",
            "/no/params/in/this/one"
        ]
        expected_results = [
            "/an/{End}/{Point}/with/{Params}",
            "/no/params/in/this/one"
        ]
        # It replaces <papi-style> URI param markers with {Swagger-style}.
        for i, test_uri in enumerate(test_uris):
            self.assertEqual(
                csc.to_swagger_end_point(test_uri),
                expected_results[i])

    def test_add_path_params(self):
        """Add path parameters."""
        test_params = [
            ('Someparametername', 'string'),
            ('Anotherparam', 'integer')]
        expected_results = [
            {
                'name': test_params[0][0],
                'in': 'path',
                'required': True,
                'type': test_params[0][1]
            },
            {
                'name': test_params[1][0],
                'in': 'path',
                'required': True,
                'type': test_params[1][1]
            }
        ]
        # It appends a param object based on specified param name and type.
        swagger_params = []
        csc.add_path_params(swagger_params, [test_params[0]])
        self.assertTrue(expected_results[0] in swagger_params)
        csc.add_path_params(swagger_params, [test_params[1]])
        self.assertTrue(expected_results[1] in swagger_params)

    def test_parse_path_params(self):
        """Parse PAPI path parameters."""
        paths = [
            '/this/uri/has/a/<parameter>',
            '/this/uri/has/a/<lnn>',
            '/this/<uri>/has/<lnn>/and/<multiple>/parameters',
            '/this/one/doesnt/have/parameters/like/that'
        ]
        # It correctly parses string parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(paths[0]),
            [('Parameter', 'string')])
        # It correctly parses integer parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(paths[1]),
            [('Lnn', 'integer')])
        # It correctly parses multiple parameters from a URI.
        self.assertEqual(
            csc.parse_path_params(paths[2]),
            [('Uri', 'string'), ('Lnn', 'integer'), ('Multiple', 'string')])
        # It returns an empty list given a URI with no params.
        self.assertEqual(csc.parse_path_params(paths[3]), [])

    def test_props_to_swagger_params(self):
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

    def test_invalid_required_field(self):
        """Remove invalid placement of required field."""
        isi_schema = {
            'properties': {
                'health_flags': {
                    'description': 'The disk pool health status.',
                    'items': {
                        'enum': [
                            'underprovisioned',
                            'missing_drives',
                            'devices_down',
                            'devices_smartfailed',
                            'waiting_repair'
                        ],
                        'required': True,
                        'type': 'string'
                    },
                    'type': 'array'
                }
            },
            'type': 'object'
        }
        expected = copy.deepcopy(isi_schema)
        del expected['properties']['health_flags']['items']['required']

        csc.isi_schema_to_swagger_object(
            'StoragepoolStatus', 'UnhealthyItem', isi_schema, {},
            'Extended', is_response_object=True)

        self.assertEqual(isi_schema, expected)

    def test_duplicate_enum(self):
        """Remove duplicate `delete_child`."""
        isi_schema = {
            'type': 'object',
            'properties': {
                'flags': {
                    'enum': [
                        'successful',
                        'failed'
                    ],
                    'type': 'string',
                    'description': 'Audit on success or failure.'
                },
                'permission': {
                    'items': {
                        'enum': [
                            'traverse', 'delete_child', 'add_file',
                            'delete_child', 'file_gen_all', 'execute'
                        ],
                        'type': 'string',
                        'description': 'Filesystem access permission.'
                    },
                    'required': True,
                    'type': 'array',
                    'description': 'Array of filesystem rights governed.'
                }
            }
        }
        expected = copy.deepcopy(isi_schema)
        expected['properties']['permission']['items']['enum'] = [
            'traverse', 'delete_child', 'add_file', 'file_gen_all', 'execute'
        ]
        del expected['properties']['permission']['required']
        expected['required'] = ['permission']

        csc.isi_schema_to_swagger_object(
            'SmbSettingsGlobalSettings', 'AuditGlobalSaclItem', isi_schema,
            {}, 'Extended', is_response_object=True)

        self.assertEqual(isi_schema, expected)

    def test_invalid_draft_style(self):
        """Update required attribute to draft 4 style."""
        isi_schema = {
            'properties': {
                'disconnected_nodes': {
                    'description': 'Devids not connected to coordinator.',
                    'items': {
                        'required': True,
                        'type': 'integer'
                    },
                    'type': 'array'
                }
            },
            'type': 'object'
        }

        expected = copy.deepcopy(isi_schema)
        del expected['properties']['disconnected_nodes']['items']['required']
        expected['required'] = ['disconnected_nodes']

        csc.isi_schema_to_swagger_object(
            'JobJob', 'Summary', isi_schema, {},
            'Extended', is_response_object=True)

        self.assertEqual(isi_schema, expected)

    def test_first_misspelling(self):
        """Correct misspelling of descriprion."""
        isi_schema = {
            'type': 'object',
            'properties': {
                'errors': {
                    'descriprion': 'The number of errors.',
                    'type': 'integer'
                },
                'calls': {
                    'descriprion': 'The number of calls.',
                    'type': 'integer'
                },
                'time': {
                    'descriprion': 'Total time spent in this method.',
                    'type': 'number'
                }
            }
        }
        expected = {
            'type': 'object',
            'properties': {
                'errors': {
                    'description': 'The number of errors.',
                    'type': 'integer'
                },
                'calls': {
                    'description': 'The number of calls.',
                    'type': 'integer'
                },
                'time': {
                    'description': 'Total time spent in this method.',
                    'type': 'number'
                }
            }
        }
        csc.isi_schema_to_swagger_object(
            'DebugStats', 'Stats', isi_schema, {},
            'Extended', is_response_object=True)

        self.assertEqual(isi_schema, expected)

    def test_second_misspelling(self):
        """Correct misspelling of descriptoin."""
        isi_schema = {
            'properties': {
                'id': {
                    'descriptoin': 'The user ID.',
                    'type': 'string'
                }
            },
            'type': 'object'
        }
        expected = {
            'properties': {
                'id': {
                    'description': 'The user ID.',
                    'type': 'string'
                }
            },
            'type': 'object'
        }
        csc.isi_schema_to_swagger_object(
            'AuthAccess', 'AccessItem', isi_schema, {},
            'Extended', is_response_object=True)

        self.assertEqual(isi_schema, expected)

    def test_invalid_stat_op_schema(self):
        """Correct stats operation properties schema."""
        isi_schema = {
            'type': 'object',
            'properties': {
                'operations': [{
                    'operation': {
                        'required': True,
                        'type': 'string',
                        'description': 'The name of the operation.'
                    }
                }]
            }
        }
        csc.isi_schema_to_swagger_object(
            'Statistics', 'Operation', isi_schema, {},
            'Extended', is_response_object=True)

        expected = {
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The name of the operation.'
                }
            },
            'required': ['operation']
        }
        self.assertEqual(isi_schema, expected)

    def test_invalid_sub_properties(self):
        """Move sub properties under properties."""
        isi_schema = {
            'description': 'Get list Tape and Changer devices',
            'properties': {
                'devices': {
                    'media_changers': {
                        'properties': {
                            'id': {
                                'description': 'Unique display id.',
                                'type': 'string'
                            }
                        },
                        'type': 'array'
                    },
                    'tapes': {
                        'properties': {
                            'serial': {
                                'description': 'Serial number',
                                'type': 'string'
                            }
                        },
                        'type': 'array'}},
                'resume': {
                    'description': 'Resume string returned by previous query.',
                    'type': 'string'
                },
                'total': {
                    'description': 'The number of devices',
                    'type': 'integer'
                }
            },
            'type': 'object'
        }
        csc.isi_schema_to_swagger_object(
            'Hardware', 'Tapes', isi_schema, {}, 'Extended')

        expected = {
            'description': 'Get list Tape and Changer devices',
            'properties': {
                'devices': {
                    '$ref': '#/definitions/HardwareTapesDevices',
                    'description': 'Information of Tape/MC device'
                },
                'resume': {
                    'description': 'Resume string returned by previous query.',
                    'type': 'string'
                },
                'total': {
                    'description': 'The number of devices',
                    'type': 'integer'
                }
            },
            'type': 'object'
        }
        self.assertEqual(isi_schema, expected)

    def test_nested_array_schema(self):
        """Correct nested array schema."""
        isi_schema = {
            'properties': {
                'causes': {
                    'description': 'List of eventgroup IDs.',
                    'items': {
                        'type': {
                            'description': 'Event Group cause.',
                            'items': {'type': 'string'},
                            'type': 'array'
                        }
                    },
                    'type': 'array'
                },
            },
            'type': 'object'
        }
        csc.isi_schema_to_swagger_object(
            'EventEventgroupOccurrences', 'Eventgroup-Occurrence',
            isi_schema, {}, 'Extended')

        expected = {
            'properties': {
                'causes': {
                    'description': 'List of eventgroup IDs.',
                    'items': {
                        'description': 'Event Group cause.',
                        'items': {'type': 'string'},
                        'type': 'array'
                    },
                    'type': 'array'
                },
            },
            'type': 'object'
        }
        self.assertEqual(isi_schema, expected)


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
