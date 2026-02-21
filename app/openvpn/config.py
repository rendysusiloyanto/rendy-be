import os

# Dapat di-override via environment
EASYRSA_DIR = os.environ.get("OPENVPN_EASYRSA_DIR", "/etc/openvpn/server/easy-rsa")
CCD_DIR = os.environ.get("OPENVPN_CCD_DIR", "/etc/openvpn/ccd")
CLIENT_OUTPUT_DIR = os.environ.get("OPENVPN_CLIENT_OUTPUT_DIR", "/root/openvpn-clients")
SERVER_CLIENT_COMMON = os.environ.get("OPENVPN_SERVER_CLIENT_COMMON", "/etc/openvpn/server/client-common.txt")

VPN_NET_PREFIX = "10.8.0."

IP_POOLS = {
    "XIII_SIJA_1": range(101, 136),
    "XIII_SIJA_2": range(136, 171),
    "GUEST": range(200, 231),
}
