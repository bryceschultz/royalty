from pickletools import StackObject
from webbrowser import get
from algosdk import *
from algosdk.v2client.algod import *
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from sandbox import get_accounts
from deploy import create_app, create_asa, delete_app

import enforcer.contract as enforcer
import marketplace.contract as marketplace


client = AlgodClient("a" * 64, "http://localhost:4001")

ZERO_ADDR = encoding.encode_address(bytes(32))

# Read in ABI description from enforcer
with open("enforcer/abi.json") as f:
    enforcer_iface = Interface.from_json(f.read())

# Read in ABI description from market
with open("marketplace/abi.json") as f:
    marketplace_iface = Interface.from_json(f.read())


# Utility method til one is provided
def get_method(i: Interface, name: str) -> Method:
    for m in i.methods:
        if m.name == name:
            return m
    raise Exception("No method with the name {}".format(name))


def dryrun(atc: AtomicTransactionComposer, client: AlgodClient):
    dr_req = create_dryrun(client, atc.gather_signatures())
    dr_resp = client.dryrun(dr_req)
    dr_result = dryrun_results.DryrunResponse(dr_resp)
    for txn in dr_result.txns:
        if txn.app_call_rejected():
            print(txn.app_trace(dryrun_results.StackPrinterConfig(max_value_width=0)))


def main():
    # Get accounts
    accts = get_accounts()

    addr, pk = accts[0]
    royalty_addr, _ = accts[1]
    buyer_addr, buyer_pk = accts[2]

    addr_signer = AccountTransactionSigner(pk)
    buyer_signer = AccountTransactionSigner(buyer_pk)

    #
    # Create Royalty Enforcer application
    #
    app_id, app_addr = create_app(
        client,
        addr,
        pk,
        enforcer.get_approval,
        enforcer.get_clear,
        global_schema=StateSchema(1, 1),
        local_schema=StateSchema(0, 16),
    )
    print("Created royalty-enforcment app {} ({})".format(app_id, app_addr))

    #
    # Create NFT
    #

    sp = client.suggested_params()
    atc = AtomicTransactionComposer()
    atc.add_transaction(
        TransactionWithSigner(
            txn=PaymentTxn(addr, sp, app_addr, int(1e8)), signer=addr_signer
        )
    )
    atc.add_transaction(
        TransactionWithSigner(
            txn=ApplicationCallTxn(addr, sp, app_id, OnComplete.OptInOC),
            signer=addr_signer,
        )
    )
    atc.add_method_call(
        app_id, get_method(enforcer_iface, "create_nft"), addr, sp, addr_signer
    )
    results = atc.execute(client, 2)

    created_nft_id = results.abi_results[0].return_value
    print("Created nft {}".format(created_nft_id))

    #
    # Set the royalty policy
    #

    print("Calling set_royalty_policy method")
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id,
        get_method(enforcer_iface, "set_royalty_policy"),
        addr,
        sp,
        addr_signer,
        method_args=[1000, royalty_addr],
    )
    atc.execute(client, 2)

    #
    # Move NFT to app creator
    #

    print("Calling move method to give asa to app creator")
    move_amount = 1
    sp = client.suggested_params()
    atc = AtomicTransactionComposer()
    # Opt in
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetTransferTxn(addr, sp, addr, 0, created_nft_id), signer=addr_signer
        )
    )
    # Move
    atc.add_method_call(
        app_id,
        get_method(enforcer_iface, "royalty_free_move"),
        addr,
        sp,
        addr_signer,
        [created_nft_id, move_amount, app_addr, addr, 0, ZERO_ADDR],
    )
    atc.execute(client, 2)

    #
    # Create Marketplace Application
    #

    print("Creating marketplace app")
    market_app_id, market_app_addr = create_app(
        client,
        addr,
        pk,
        marketplace.get_approval,
        marketplace.get_clear,
        global_schema=StateSchema(4, 1),
        local_schema=StateSchema(0, 16),
    )
    print("Created marketplace app: {} ({})".format(market_app_id, market_app_addr))

    #
    # List NFT for sale on marketplace
    #

    price = int(2e6)
    offered_amount = 1

    print("Calling list method on marketplace")

    # We construct an ATC with no intention of submitting it as is
    # we're just using it to parse/marshal in the app args
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id,
        get_method(enforcer_iface, "offer"),
        addr,
        sp,
        addr_signer,
        [created_nft_id, offered_amount, market_app_addr, 0, ZERO_ADDR],
    )
    grp = atc.build_group()

    # Construct the list app call, passing the offer app call built previously
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        market_app_id,
        get_method(marketplace_iface, "list"),
        addr,
        sp,
        addr_signer,
        [created_nft_id, app_id, offered_amount, price, grp[0]],
    )

    # dryrun(atc, client)
    # return

    atc.execute(client, 2)
    print("Listed asset for sale")

    #
    # Buyer calls buy method
    #

    print("Calling buy method on marketplace")
    atc = AtomicTransactionComposer()
    txn = TransactionWithSigner(
        txn=PaymentTxn(buyer_addr, sp, market_app_addr, price),
        signer=buyer_signer,
    )
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetOptInTxn(buyer_addr, sp, created_nft_id), signer=buyer_signer
        )
    )
    atc.add_method_call(
        market_app_id,
        get_method(marketplace_iface, "buy"),
        buyer_addr,
        sp,
        buyer_signer,
        [created_nft_id, app_id, app_addr, addr, royalty_addr, offered_amount, txn],
    )

    #dryrun(atc, client)
    #return
    atc.execute(client, 2)
    print("Bought ASA")

    # Balances should all match up


if __name__ == "__main__":
    main()
