# --- file: utils/invoice_utils.py ---

from PIL import Image
import io
import hashlib
from collections import OrderedDict


# ==============================
# IMAGE OPTIMIZATION
# ==============================
def compress_image(file, max_size=(1024, 1024), quality=70, grayscale=False):
    """
    Resize and compress image safely for Streamlit Cloud.
    """
    try:
        file_bytes = file.getvalue()
        if not file_bytes:
            raise ValueError("Empty file received")

        image = Image.open(io.BytesIO(file_bytes))

        # Handle transparency
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background

        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Resize safely
        image.thumbnail(max_size, Image.LANCZOS)

        if grayscale:
            image = image.convert("L")

        buffer = io.BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=max(30, min(quality, 95)),
            optimize=True
        )
        buffer.seek(0)

        return buffer

    except Exception as e:
        raise RuntimeError(f"Image compression failed: {str(e)}")


# ==============================
# FILE HASHING
# ==============================
def get_file_hash(file):
    """
    Generate unique hash for file.
    """
    try:
        file_bytes = file.getvalue()
        if not file_bytes:
            raise ValueError("Empty file for hashing")

        return hashlib.sha256(file_bytes).hexdigest()

    except Exception as e:
        raise RuntimeError(f"File hashing failed: {str(e)}")


# ==============================
# CACHE (LRU + SAFE)
# ==============================
def init_cache(session_state, limit=5):
    """
    Initialize LRU cache in session_state.
    """
    if "cache" not in session_state:
        session_state.cache = OrderedDict()


def get_cached_result(file_hash, cache_dict):
    """
    Retrieve and update usage order.
    """
    if not cache_dict or file_hash not in cache_dict:
        return None

    cache_dict.move_to_end(file_hash)
    return cache_dict[file_hash]


def set_cached_result(file_hash, result, cache_dict, limit=5):
    """
    Store result with LRU eviction.
    """
    if cache_dict is None:
        return

    cache_dict[file_hash] = result
    cache_dict.move_to_end(file_hash)

    # Strict memory cap
    while len(cache_dict) > limit:
        cache_dict.popitem(last=False)


# ==============================
# FILE SIZE
# ==============================
def get_file_size_kb(file):
    try:
        file_bytes = file.getvalue()
        if not file_bytes:
            return 0.0

        return round(len(file_bytes) / 1024, 2)

    except Exception:
        return 0.0