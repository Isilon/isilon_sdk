# isilon-swagger
Tools to allow integration of Isilon REST APIs with Swagger (swagger.io)

#### To generate a swagger config for PAPI:

1. Clone this repository.
2. Find a OneFS cluster, get the IP address.
3. Run `python create_swagger_config.py -i <cluster-ip-address> -o <output_file> --username <username> --password <password>` <br> if you omit --username or --password then it will prompt you

This will automatically generate a swagger config <output_file> based on the ?describe responses from the PAPI handlers on your node.  Swagger tools can now use this config to create language bindings and documentation.

#### To generate python PAPI bindings using the swagger config:
1. Clone the swagger-codegen repo from https://github.com/swagger-api/swagger-codegen
2. Follow the relevant instructions there (in the README.md) to install the codegen java program.  In my case I did "apt-get install maven" to get maven then ran "mvn package" to install codegen.
3. Run codegen on the swagger_config.json file generated above.  You can also use one of the "example_output.json" available in the root directory of this repo.  For example:

`java -jar modules/swagger-codegen-cli/target/swagger-codegen-cli.jar generate -i output.json -l python -o ./papi_client/python`

#### To generate API documentation from the swagger config:
1. Generate a PAPI swagger config as above, or use the "example_output.json" in this repo.
2. Install codegen as described above.
3. Use codegen with the language specified as "nodejs" or "html" to output API docs instead of a bindings library for a language, for example:

``java -jar modules/swagger-codegen-cli/target/swagger-codegen-cli.jar generate -i swagger_config.json -l dynamic-html -o ./papi_doc`

Note that you do not need to have NodeJS installed to browse the "nodejs" style dynamic output docs - just go into the generated directory structure, find index.html, and open it in your browser.  You can see an example of my most recently generated docs at:

`http://cribsbiox.west.isilon.com/home/bwilkins/swagger/papi_doc_dynamic/docs/`

#### To write code with the python PAPI bindings:
1. Generate a python PAPI bindings package using the above steps, or just use the one I've put at `http://cribsbiox.west.isilon.com/home/bwilkins/swagger/papi_client/python/`
2. Install the library with `python setup.py install --user` from the `papi_client` directory
3. In your python programs, you can now write code like the following to interact with PAPI handlers:

```
import swagger_client
import urllib3
urllib3.disable_warnings()

# configure username and password
swagger_client.configuration.username = "root"
swagger_client.configuration.password = "a"
swagger_client.configuration.verify_ssl = False

# configure host
host = "https://10.7.160.60:8080"
apiClient = swagger_client.ApiClient(host)
protocolsApi = swagger_client.ProtocolsApi(apiClient)

# get all exports
nfsExports = protocolsApi.list_nfs_exports()
print "NFS Exports:\n" + str(nfsExports)

```

For more examples of coding to the python PAPI bindings, see the test scripts in the `tests/` subdirectory of this repo.

As you code, you may want to generate docs with the steps above, or refer to the docs I generated and put at:

`http://cribsbiox.west.isilon.com/home/bwilkins/swagger/papi_doc_dynamic/docs/`

In some cases just looking at the actual swagger config will be more informative though because currently the generated "NodeJS" style docs obscure the full format of a lot of PAPI's return objects.  I'm looking into different swagger documentation tools.
