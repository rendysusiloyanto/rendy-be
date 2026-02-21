import subprocess
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from app.auth import get_current_user_premium
from app.models.user import User
from app.openvpn import create_openvpn_client, read_openvpn_client, get_openvpn_status

router = APIRouter(prefix="/api/openvpn", tags=["openvpn"])


@router.get("/status")
def get_status(user: User = Depends(get_current_user_premium)):
    """
    Cek apakah user sudah punya config OpenVPN. Email diambil dari session.
    Hanya untuk akun premium.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    try:
        return get_openvpn_status(email=email)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal cek status: {e!s}",
        )


def _vpn_role(user: User) -> str:
    """Map class_name ke role pool OpenVPN. Default GUEST."""
    name = (user.class_name or "").strip().upper().replace(" ", "_")
    from app.openvpn.config import IP_POOLS
    if name in IP_POOLS:
        return name
    return "GUEST"


@router.post("/create")
def create_config(user: User = Depends(get_current_user_premium)):
    """
    Buat config OpenVPN untuk user yang login. Email diambil dari session.
    Hanya untuk akun premium. Gagal jika config sudah ada.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    vpn_status = get_openvpn_status(email=email)
    if vpn_status.get("has_config"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Config OpenVPN sudah ada. Gunakan tombol Download.",
        )
    try:
        role = _vpn_role(user)
        result = create_openvpn_client(email=email, role=role)
        return {
            "message": "Config OpenVPN berhasil dibuat.",
            "username": result["username"],
            "ip": result["ip"],
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat sertifikat OpenVPN. Hubungi admin.",
        )
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sistem: {e!s}",
        )


@router.get("/config", response_class=Response)
def get_config(user: User = Depends(get_current_user_premium)):
    """
    Download file .ovpn untuk user yang login. Email diambil dari session.
    Hanya untuk akun premium.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    try:
        content = read_openvpn_client(email=email)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca file: {e!s}",
        )

    filename = f"{user.email.split('@')[0].replace('.', '_')}.ovpn"
    return Response(
        content=content,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
