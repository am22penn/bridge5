from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
from web3.middleware import geth_poa_middleware #Necessary for POA chains
import json
import sys
from pathlib import Path
import eth_account
from eth_account import Account
import os
import pandas as pd

source_chain = 'avax'
destination_chain = 'bsc'
contract_info = "contract_info.json"

def connectTo(chain):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['avax','bsc']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    """
        Load the contract_info file into a dictinary
        This function is used by the autograder and will likely be useful to you
    """
    p = Path(__file__).with_name(contract_info)
    try:
        with p.open('r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( "Failed to read contract info" )
        print( "Please contact your instructor" )
        print( e )
        sys.exit(1)

    return contracts[chain]

def scanBlocks(chain):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return
    
    #YOUR CODE HERE
    w3_source = connectTo(source_chain)
    w3_destination = connectTo(destination_chain)

    source_contract_info = getContractInfo(source_chain)
    destination_contract_info = getContractInfo(destination_chain)

    source_contract = w3_source.eth.contract(address=source_contract_info['address'], abi=source_contract_info['abi'])
    destination_contract = w3_destination.eth.contract(address=destination_contract_info['address'], abi=destination_contract_info['abi'])

    latest_block = w3_source.eth.get_block_number() if chain == "source" else w3_destination.eth.get_block_number()

    start_block = latest_block - 5
    end_block = latest_block

    if chain == 'source':
        event_filter = source_contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()
        for event in events:
            with open('eth_mnemonic.txt', 'r') as f:
                mnemonic = f.readline().strip()
            acct = Account.from_key(mnemonic)
            nonce = w3_destination.eth.get_transaction_count(acct.address)
            tx = destination_contract.functions.wrap(event['args']['token'], event['args']['recipient'], event['args']['amount']).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': w3_destination.to_wei('10', 'gwei')
            })
            signed_tx = w3_destination.eth.account.sign_transaction(tx, mnemonic)
            tx_hash = w3_destination.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"Wrapped tokens on {destination_chain}: {tx_hash.hex()}")

    elif chain == 'destination':
        event_filter = destination_contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()
        for event in events:
            with open('eth_mnemonic.txt', 'r') as f:
                mnemonic = f.readline().strip()
            acct = Account.from_key(mnemonic)
            nonce = w3_source.eth.get_transaction_count(acct.address)
            tx = source_contract.functions.withdraw(event['args']['underlying_token'], event['args']['to'], event['args']['amount']).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': w3_source.to_wei('10', 'gwei')
            })
            signed_tx = w3_source.eth.account.sign_transaction(tx, mnemonic)
            tx_hash = w3_source.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"Withdrew tokens on {source_chain}: {tx_hash.hex()}")

if __name__ == "__main__":
    scanBlocks("source")
    scanBlocks("destination")