# Isilon Software Development Kit (isi-sdk)
Building language bindings using the OpenAPI config generator

This document describes how to use the scripts in the isilon_sdk repository to generate your own language bindings for the Isilon OneFS configuration API.  This API is made up of all the URIs underneath `https://[cluster]:8080/platform/*`, also called the "Platform API" or "PAPI".  This API also includes the URIs underneath `https://[cluster]:8080/namespace/*`, also called the "RESTful Access to Namespace" or "RAN".

The scripts create a configuration file compatible with the OpenAPI Specification (formerly known as swagger, and we will continue to call the configuration file the "swagger config" here for now).  More info about the OpenAPI Specification [here](https://github.com/OAI/OpenAPI-Specification).

The swagger config can then be used by the [swagger codegen tool](https://github.com/swagger-api/swagger-codegen) to generate language bindings for [various languages](https://github.com/swagger-api/swagger-codegen#customizing-the-generator).  This is how the Python bindings in the "releases" page of this repo are generated when updates to our scripts are made.  If you just need the Python bindings, you can download the latest from the "releases" page (the link is on the main "code" tab of the github repo on the bar of links just below the project description).

The walkthrough below will guide you through the generation process step by step in case you want to build your own bindings.  You will need access to a cluster running OneFS version 7.2 or later (earlier versions not tested).

### To generate the swagger config for PAPI:

1. Clone this repository.
2. Find a OneFS cluster, get the IP address.
3. Run `python components/create_swagger_config.py -i <cluster-ip-address> -o <output_file> --username <username> --password <password>` <br> if you omit --username or --password then it will prompt you

This will automatically generate a swagger config `<output_file>` based on the ?describe responses from the PAPI handlers on your node.  Swagger tools can now use this config to create language bindings and documentation.

### To generate PAPI bindings for Python or other languages using the swagger config:
1. Clone the swagger-codegen repo from https://github.com/swagger-api/swagger-codegen.  You can try the latest version of that code, or if you want to use the last version we've tested as of this writing, it is the [v2.3.1](https://github.com/swagger-api/swagger-codegen/releases/tag/v2.3.1) release.
2. Follow the relevant instructions there (in the README.md) to install the codegen java program.  In our case we used "apt-get install maven" to get maven then ran "mvn package" to install codegen.
3. Copy the `<output_file>` file generated above (or one of the pre-made "example_output.json" files) and "swagger-codegen-config.json" from your isi_sdk root directory to your swagger-codegen root directory.
4. Run codegen on `<output_file>`.  For example, from your swagger-codegen root directory, use:

`java -jar modules/swagger-codegen-cli/target/swagger-codegen-cli.jar generate -i swagger-config.json -l python -o ./isi_sdk -c swagger-codegen-config.json -t swagger_templates/python`

For other languages, substitute the name of the language you want for `python`.  This will create a language bindings library you can install in the `./isi_sdk` subdirectory.

Documentation for the bindings should be generated along with the bindings themselves.  For the Python version, the documentation table of contents is will be in the README.md file in the root of your generated bindings ("./isi_sdk" in the example above).

### Contributing to the isi-sdk OpenAPI config generator

If you have a patch for the config generator scripts that improves the generated swagger config and the bindings that come from it, please submit a pull request to this repository.  We will review it and once the patch is accepted the bindings will be automatically rebuilt and published as a new release.

### Custom swagger-codegen templates

In some cases the standard [swagger-codegen templates](https://github.com/swagger-api/swagger-codegen/tree/master/modules/swagger-codegen/src/main/resources/python) may not be suitable with the OneFS API, necessitating the use of [custom templates](https://github.com/swagger-api/swagger-codegen/wiki/Building-your-own-Templates). Some [Python templates](./swagger_templates/python) for example, have been customized for generation of the Isilon SDK. Customized templates are located in `/swagger_templates/<language>`. This naming convention allows the automated build process to locate and use the appropriate custom templates. If no custom template exists for a language, the default template will be used automatically.
