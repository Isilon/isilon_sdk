import urllib3

import isi_sdk_8_0 as isi_sdk

import test_constants

urllib3.disable_warnings()


def main():
    # configure username and password
    configuration = isi_sdk.Configuration()
    configuration.username = test_constants.USERNAME
    configuration.password = test_constants.PASSWORD
    configuration.verify_ssl = test_constants.VERIFY_SSL
    configuration.host = test_constants.HOST

    # configure client connection
    api_client = isi_sdk.ApiClient(configuration)
    antivirus_api = isi_sdk.AntivirusApi(api_client)

    # create a new policy
    new_policy = isi_sdk.AntivirusPolicy()
    new_policy.paths = ["/ifs/data/Isilon_Support"]
    new_policy.name = "ifs_data_support"

    # use force because path already exists as policy so would normally fail
    create_resp = antivirus_api.create_antivirus_policy(new_policy)
    print("Created=" + str(create_resp.id))

    # get it by id
    get_policy_resp = antivirus_api.get_antivirus_policy(create_resp.id)

    # update it with a PUT
    policy = get_policy_resp.policies[0]

    update_policy = isi_sdk.AntivirusPolicy()

    # toggle the browsable parameter
    update_policy.enabled = not policy.enabled

    antivirus_api.update_antivirus_policy(antivirus_policy_id=policy.id,
                                          antivirus_policy=update_policy)


    # get it back and check that it worked
    get_policy_resp = antivirus_api.get_antivirus_policy(policy.id)

    print("It worked == " +
          str(get_policy_resp.policies[0].enabled == update_policy.enabled))

    # get all policies
    antivirus_policies = antivirus_api.list_antivirus_policies()
    print("Antivirus Policies:\n" + str(antivirus_policies))

    # now delete it
    print("Deleting it.")
    antivirus_api.delete_antivirus_policy(antivirus_policy_id=create_resp.id)

    # verify that it is deleted
    # Note: my Error data model is not correct yet,
    # so get on a non-existent antivirus policy id throws exception.
    # Ideally it would just return an error response
    try:
        print("Verifying delete.")
        resp = antivirus_api.get_antivirus_policy(
            antivirus_policy_id=create_resp.id)
        print("Response should be 404, not: " + str(resp))
    except isi_sdk.rest.ApiException:
        pass

    print("Done.")


if __name__ == '__main__':
    main()
