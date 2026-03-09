from io import BytesIO
from typing import Tuple, Union, Dict
from PIL import Image

ALLOWED_FORMATS = {"JPEG", "PNG", "GIF"}

def validate_image(data: bytes, mime: str, max_size_mb: int = 10, max_dim_px: int = 4096) -> Tuple[bool, Union[str, Dict[str, Union[int, str]]]]:
    size_bytes = len(data)
    if size_bytes > max_size_mb * 1024 * 1024:
        return False, f"Arquivo excede {max_size_mb}MB"
    try:
        img = Image.open(BytesIO(data))
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            return False, f"Formato inválido: {fmt or mime}"
        w, h = img.size
        if w > max_dim_px or h > max_dim_px:
            return False, f"Dimensões acima de {max_dim_px}px ({w}x{h})"
        if w < 32 or h < 32:
            return False, "Dimensões muito pequenas (mínimo 32x32)"
        return True, {"width": w, "height": h, "format": fmt}
    except Exception as e:
        return False, f"Falha ao processar imagem: {e}"
