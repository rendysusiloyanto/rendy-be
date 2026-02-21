import os
import subprocess
from app.openvpn.config import (
    EASYRSA_DIR,
    CCD_DIR,
    CLIENT_OUTPUT_DIR,
    SERVER_CLIENT_COMMON,
)
from app.openvpn.ip_allocator import allocate_ip


def sanitize_username(email: str) -> str:
    return email.split("@")[0].replace(".", "_")


def create_openvpn_client(email: str, role: str) -> dict:
    """Buat client OpenVPN. Raises ValueError, RuntimeError, FileNotFoundError, subprocess.CalledProcessError."""
    username = sanitize_username(email)

    if not os.path.isdir(EASYRSA_DIR):
        raise FileNotFoundError(f"EasyRSA directory not found: {EASYRSA_DIR}")
    if not os.path.isfile(SERVER_CLIENT_COMMON):
        raise FileNotFoundError(f"Server client-common not found: {SERVER_CLIENT_COMMON}")

    ip = allocate_ip(role)

    os.makedirs(CLIENT_OUTPUT_DIR, exist_ok=True)
    os.makedirs(CCD_DIR, exist_ok=True)

    easyrsa = os.path.join(EASYRSA_DIR, "easyrsa")
    if not os.path.isfile(easyrsa):
        raise FileNotFoundError(f"easyrsa not found: {easyrsa}")

    subprocess.run(
        [
            easyrsa,
            "--batch",
            "--days=3650",
            "build-client-full",
            username,
            "nopass",
        ],
        cwd=EASYRSA_DIR,
        check=True,
        capture_output=True,
        text=True,
    )

    ovpn_path = os.path.join(CLIENT_OUTPUT_DIR, f"{username}.ovpn")
    private_inline = os.path.join(EASYRSA_DIR, "pki", "inline", "private", f"{username}.inline")
    if not os.path.isfile(private_inline):
        raise FileNotFoundError(f"Generated inline key not found: {private_inline}")

    with open(ovpn_path, "w") as out:
        subprocess.run(
            [
                "grep",
                "-vh",
                "^#",
                SERVER_CLIENT_COMMON,
                private_inline,
            ],
            stdout=out,
            check=True,
        )

    ccd_path = os.path.join(CCD_DIR, username)
    with open(ccd_path, "w") as f:
        f.write(f"ifconfig-push {ip} 255.255.255.0\n")

    return {
        "username": username,
        "email": email,
        "ip": ip,
        "ovpn": ovpn_path,
        "ccd": ccd_path,
    }


def read_openvpn_client(email: str) -> str:
    """Baca isi file .ovpn client. Raises FileNotFoundError jika belum pernah dibuat."""
    username = sanitize_username(email)
    ovpn_path = os.path.join(CLIENT_OUTPUT_DIR, f"{username}.ovpn")
    if not os.path.exists(ovpn_path):
        raise FileNotFoundError(f"OpenVPN config belum dibuat untuk email ini. Buat config dulu.")
    with open(ovpn_path, "r") as f:
        return f.read()


def get_openvpn_status(email: str) -> dict:
    """
    Cek apakah user sudah punya config OpenVPN.
    Returns: { "has_config": bool, "username": str | None, "ip": str | None }
    """
    username = sanitize_username(email)
    ovpn_path = os.path.join(CLIENT_OUTPUT_DIR, f"{username}.ovpn")
    if not os.path.isfile(ovpn_path):
        return {"has_config": False, "username": None, "ip": None}

    ip = None
    ccd_path = os.path.join(CCD_DIR, username)
    if os.path.isfile(ccd_path):
        try:
            with open(ccd_path, "r") as f:
                for line in f:
                    if line.startswith("ifconfig-push"):
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[1]
                        break
        except (OSError, IOError):
            pass

    return {"has_config": True, "username": username, "ip": ip}
