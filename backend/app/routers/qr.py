"""QR de direcciones (wallet/contrato) como PNG escaneable."""
import io
import re
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter()

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def make_qr_png(text: str, box_size: int = 10, border: int = 4) -> bytes:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=max(4, min(int(box_size), 20)),
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/qr/{address}")
def qr_address(
    address: str,
    size: int = Query(default=10, ge=4, le=20),
    download: bool = False,
):
    """PNG con QR de la dirección (texto = dirección cruda, compatible con wallets)."""
    if not ADDR_RE.match(address):
        raise HTTPException(status_code=400, detail="dirección inválida: se espera 0x + 40 hex")
    png = make_qr_png(address, box_size=size)
    headers = {}
    if download:
        headers["Content-Disposition"] = f"attachment; filename=qr-{address[:12]}.png"
    return Response(content=png, media_type="image/png", headers=headers)
