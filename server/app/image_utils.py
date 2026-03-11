"""
Image Utilities for LegacyBridge Backend
------------------------------------------
Handles all image processing tasks for the /process-screen endpoint:
  - Fast JPEG compression with configurable quality
  - Perceptual hashing (pHash) to detect duplicate/near-duplicate screenshots
  - Resize-before-hash to ensure consistent comparison regardless of capture size

Why perceptual hashing?
  Most of the time the screen doesn't change between 2-second captures.
  Instead of sending every frame to Gemini (expensive + slow), we compute a
  compact 64-bit hash of the image and compare it to the previous one.
  If the hash distance is very small, the screen is basically the same —
  we return the cached response instantly without an API call.
"""

import io
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

# Executor for running CPU-bound Pillow operations off the async event loop
_executor = ThreadPoolExecutor(max_workers=2)

# Target resolution for hashing — small enough to be fast, big enough to catch changes
_HASH_SIZE = 8   # produces 64-bit hash
_HASH_THUMB = (32, 32)

# Max allowed Hamming distance between hashes to consider screens "the same"
# 0 = identical, higher = more tolerant of minor changes
SIMILARITY_THRESHOLD = int(3)


def _compute_phash(image: Image.Image) -> str:
    """
    Compute a perceptual hash (average hash / aHash) of the image.
    Returns a 64-character hex string representing the hash.

    Algorithm:
    1. Resize to 8x8 grayscale (64 pixels total)
    2. Compute average pixel brightness
    3. Set each bit to 1 if pixel > average, else 0
    4. Return as hex string
    """
    grayscale = image.convert("L").resize((_HASH_SIZE, _HASH_SIZE), Image.LANCZOS)
    pixels = list(grayscale.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    # Pack bits into integer then format as hex
    hash_int = int(bits, 2)
    return f"{hash_int:016x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Count the number of differing bits between two hex hash strings."""
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    xor = int1 ^ int2
    return bin(xor).count("1")


def is_similar(hash1: str, hash2: str) -> bool:
    """Return True if two image hashes are similar enough to skip re-processing."""
    return hamming_distance(hash1, hash2) <= SIMILARITY_THRESHOLD


def compress_image_to_bytes(image: Image.Image, quality: int = 75) -> bytes:
    """
    Convert a PIL Image to optimised JPEG bytes for Vertex AI.
    - Caps resolution at 1280x720 (Gemini doesn't need more)
    - Uses progressive JPEG encoding for slightly better compression
    """
    # Resize if too large
    image.thumbnail((1280, 720), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


async def process_image_async(raw_bytes: bytes) -> tuple[Image.Image, bytes, str]:
    """
    Run all image processing in a thread pool to avoid blocking the event loop.
    Returns: (pil_image, compressed_bytes, phash)
    """
    loop = asyncio.get_event_loop()

    def _process():
        image = Image.open(io.BytesIO(raw_bytes))
        compressed = compress_image_to_bytes(image)
        phash = _compute_phash(image)
        return image, compressed, phash

    return await loop.run_in_executor(_executor, _process)
