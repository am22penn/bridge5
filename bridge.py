from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
from web3.middleware import geth_poa_middleware #Necessary for POA chains
import json
import sys
from pathlib import Path

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

    if chain == 'source':
        current_chain = source_chain
        other_chain = destination_chain
        event_name = 'Deposit'
        function_name = 'wrap'
    else:
        current_chain = destination_chain
        other_chain = source_chain
        event_name = 'Unwrap'
        function_name = 'withdraw'
    
    w3_current = connectTo(current_chain)
    w3_other = connectTo(other_chain)

    contract_info_current = getContractInfo(current_chain)
    contract_address_current = contract_info_current['address']
    contract_abi_current = contract_info_current['abi']
    warden_private_key = contract_info_current['private_key']

    contract_info_other = getContractInfo(other_chain)
    contract_address_other = contract_info_other['address']
    contract_abi_other = contract_info_other['abi']

    contract_current = w3_current.eth.contract(address=contract_address_current, abi=contract_abi_current)
    contract_other = w3_other.eth.contract(address=contract_address_other, abi=contract_abi_other)

    latest_block = w3_current.eth.block_number
    start_block = max(0, latest_block - 5)
    end_block = latest_block

    event_signature_hash = w3_current.sha3(text=f"{event_name}(address,address,uint256)").hex()
    event_filter = {'fromBlock': start_block, 'toBlock': end_block, 'address': contract_address_current, 'topics': [event_signature_hash]}

    logs = w3_current.eth.get_logs(event_filter)

    for log in logs:
        event = contract_current.events[event_name]().processLog(log)
        token = event['args']['token']
        recipient = event['args']['recipient']
        amount = event['args']['amount']

        nonce = w3_other.eth.get_transaction_count(contract_info_current['public_key'])
        gas_price = w3_other.eth.gas_price
        gas_limit = 500000

        if function_name == 'wrap':
            tx = contract_other.functions.wrap(token, recipient, amount).buildTransaction({'from': contract_info_current['public_key'], 'nonce': nonce, 'gas': gas_limit, 'gasPrice': gas_price, 'chainId': w3_other.eth.chain_id})
        elif function_name == 'withdraw':
            tx = contract_other.functions.withdraw(token, recipient, amount).buildTransaction({'from': contract_info_current['public_key'], 'nonce': nonce, 'gas': gas_limit, 'gasPrice': gas_price, 'chainId': w3_other.eth.chain_id})
        else:
            continue

        signed_tx = w3_other.eth.account.sign_transaction(tx, private_key=warden_private_key)
        tx_hash = w3_other.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"Transaction sent to {other_chain} with hash: {tx_hash.hex()}")
        tx_receipt = w3_other.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Transaction receipt: {tx_receipt}")