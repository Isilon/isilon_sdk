import json
import urllib3

import isi_sdk_8_1_0 as isi_sdk

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
    protocols_api = isi_sdk.ProtocolsApi(api_client)

    # get all shares
    smb_shares = protocols_api.list_smb_shares()
    print("SMB Shares:\n" + str(smb_shares))

    # get a specific share by id
    get_share_resp = protocols_api.get_smb_share(smb_shares.shares[-1].id)

    # update it with a PUT
    a_share = get_share_resp.shares[0]
    update_share = isi_sdk.SmbShare()

    # toggle the browsable parameter
    update_share.browsable = not a_share.browsable

    protocols_api.update_smb_share(smb_share_id=a_share.id,
                                   smb_share=update_share)

    # get it back and check that it worked
    get_share_resp = protocols_api.get_smb_share(a_share.id)

    print("It worked == " +
          str(get_share_resp.shares[0].browsable == update_share.browsable))

    # create a new share
    new_share = isi_sdk.SmbShareCreateParams(name="ifs_data", path="/ifs/data")

    try:
        create_resp = protocols_api.create_smb_share(new_share)
    except isi_sdk.rest.ApiException as err:
        if err.status == 409:
            print(json.loads(err.body)['errors'][0]['message'])
            # share already exists, so look it up
            for share in protocols_api.list_smb_shares().shares:
                if share.name == new_share.name:
                    share_id = share.id
        else:
            raise err
    else:
        share_id = create_resp.id
        print("Created=" + str(share_id))

    # now delete it
    print("Deleting it.")
    protocols_api.delete_smb_share(smb_share_id=share_id)

    # verify that it is deleted
    try:
        print("Verifying delete.")
        protocols_api.get_smb_share(smb_share_id=share_id)
    except isi_sdk.rest.ApiException as err:
        if err.status == 404:
            print("Delete verified")
        else:
            print(err)

    print("Done.")


if __name__ == '__main__':
    main()
