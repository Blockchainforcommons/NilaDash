import streamlit as st
import pandas as pd
import json
import base64
import requests
from web3 import Web3
import json
import folium
from streamlit_folium import folium_static

# Polygon Amoy RPC
RPC_URL = "https://rpc-amoy.polygon.technology"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract Addresses
UNION_CONTRACT = "0xCF4AEdE5075B63e68AC588fc537bcbca49990B5f"
NILA_CONTRACT = "0x10D11eDD572ccb54D6D59f07521eA071Ed1C326E"
LAND_CONTRACT = "0x663DC13009D004aF3654a45f22A215De71633918"

# Load ABI from JSON files
def load_abi(file_name):
    with open(file_name, "r") as f:
        return json.load(f)

# Load ABIs
NILA_ABI = load_abi("abis/NilaToken.json")
LAND_ABI = load_abi("abis/NilaLandTitle.json")

# Connect to Contracts
nila_contract = w3.eth.contract(address=w3.to_checksum_address(NILA_CONTRACT), abi=NILA_ABI)
land_contract = w3.eth.contract(address=w3.to_checksum_address(LAND_CONTRACT), abi=LAND_ABI)

# Function to get POL balance
def get_pol_balance(address):
    return w3.eth.get_balance(address) / 1e18  # Convert to ETH units

# Function to get ERC-20 balance
def get_nila_balance(address):
    return nila_contract.functions.balanceOf(address).call() / 1e18

# Function to check ERC-721 ownership
def has_land_nft(address):
    return land_contract.functions.balanceOf(address).call() > 0

# Function to ge the farm name stored in the title
def get_land_nft_title(token_id):
    return land_contract.functions.getTitleName(token_id).call()

# Function to fetch addresses interacting with the NILA contract
def get_nila_holders():
    latest_block = w3.eth.block_number  # Get latest block number
    from_block = max(0, latest_block - 100000)  # Limit to last 50,000 blocks

    event_signature_hash =  '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef' #w3.keccak(text="Transfer(address,address,uint256)").hex()
    try:
        logs = w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": "latest",
            "address": NILA_CONTRACT,
            "topics": [event_signature_hash]
        })

        addresses = set()
        for log in logs:
            decoded_log = nila_contract.events.Transfer().process_log(log)
            addresses.add(decoded_log["args"]["from"])
            addresses.add(decoded_log["args"]["to"])

        return list(addresses)

    except Exception as e:
        print(f"Error fetching NILA holders: {e}")
        return []

def get_land_nft_metadata(owner_address):
    token_id = land_contract.functions.tokenOfOwnerByIndex(owner_address, 0).call()
    token_uri = land_contract.functions.tokenURI(token_id).call()

    # Check if tokenURI is Base64-encoded JSON
    if token_uri.startswith("data:application/json;base64,"):
        base64_data = token_uri.split(",")[1]  # Extract Base64 part
        decoded_json = base64.b64decode(base64_data).decode("utf-8")  # Decode JSON

        # Get the title name from the contract
        title_name = get_land_nft_title(token_id)

        return {
            "token_id": token_id,
            "title": title_name,
            "coords": json.loads(decoded_json)    # Assuming coords are in decoded JSON
        }

    else:
        print(f"Unexpected tokenURI format: {token_uri}")

# Fetch all members
addresses = get_nila_holders()
print('addresess', addresses)

# Fetch balances
data = []
for addr in addresses:
    meta = ''
    title = ''
    hasLand = has_land_nft(addr)
    if hasLand:
        res = get_land_nft_metadata(addr)
        print('res', res)
        meta = res['coords']
        title = res['title']


    data.append({
        "Farm Name": title,
        "Address": addr,
        "POL Balance": get_pol_balance(addr),
        "NILA Balance": get_nila_balance(addr),
        "Has LAND NFT": hasLand,
        "LAND META": json.dumps(meta),
    })

df = pd.DataFrame(data)

print('df', df)

# Streamlit Dashboard
st.title("Union Contract Members Dashboard")

st.subheader("Member Holdings")
st.dataframe(df)

# Map LAND NFTs
st.subheader("LAND NFT Locations")
map_ = folium.Map(location=[11.889743, 78.966923], zoom_start=11, tiles="Esri WorldImagery")

for _, row in df.iterrows():
    if row["Has LAND NFT"]:
        print('row', row["LAND META"])
        folium.Polygon(locations=json.loads(row["LAND META"]), tooltip=row["Farm Name"]).add_to(map_)

folium_static(map_)