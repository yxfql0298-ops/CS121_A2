"""
SimHash implementation from scratch (no external libraries).

Algorithm:
1. Tokenize the text into n-grams (or words).
2. For each token, compute a hash h(token) -> 64-bit integer.
3. For each bit position b in [0, 63]:
   - Add weight +1 if bit b of h(token) is 1, else -1.
4. The SimHash fingerprint: bit b = 1 if v[b] > 0, else 0.
5. Near-duplicate detection: two pages are near-duplicates if
   hamming_distance(fp_a, fp_b) <= SIMHASH_THRESHOLD.

We use a simple but effective 64-bit FNV-1a hash for step 2.
"""

SIMHASH_BITS = 64
SIMHASH_THRESHOLD = 3   # pages with hamming distance <= 3 are near-duplicates


# ---------------------------------------------------------------------------
# Low-level hash: 64-bit FNV-1a
# ---------------------------------------------------------------------------

FNV_PRIME_64 = 0x00000100000001B3
FNV_OFFSET_64 = 0xCBF29CE484222325
MASK_64 = (1 << 64) - 1


def _fnv1a_64(text: str) -> int:
    """Pure-Python 64-bit FNV-1a hash. Returns an unsigned 64-bit integer."""
    h = FNV_OFFSET_64
    for byte in text.encode("utf-8", errors="replace"):
        h = ((h ^ byte) * FNV_PRIME_64) & MASK_64
    return h


# ---------------------------------------------------------------------------
# SimHash core
# ---------------------------------------------------------------------------

def simhash(words: list[str], shingle_size: int = 3) -> int:
    """
    Compute a 64-bit SimHash fingerprint from a list of words.

    We use overlapping character shingles of size `shingle_size` built from
    the joined word sequence. This captures local word-order similarity better
    than plain word hashing.

    Args:
        words:        Tokenised, lower-cased word list (stop-words removed).
        shingle_size: Number of *words* per shingle (default 3).

    Returns:
        A 64-bit integer fingerprint, or 0 for empty input.
    """
    if not words:
        return 0

    # Build word-level shingles
    if len(words) < shingle_size:
        shingles = [" ".join(words)]
    else:
        shingles = [
            " ".join(words[i: i + shingle_size])
            for i in range(len(words) - shingle_size + 1)
        ]

    # Weighted bit-vector
    v = [0] * SIMHASH_BITS
    for shingle in shingles:
        h = _fnv1a_64(shingle)
        for bit in range(SIMHASH_BITS):
            if (h >> bit) & 1:
                v[bit] += 1
            else:
                v[bit] -= 1

    # Build fingerprint
    fingerprint = 0
    for bit in range(SIMHASH_BITS):
        if v[bit] > 0:
            fingerprint |= (1 << bit)
    return fingerprint


def hamming_distance(fp_a: int, fp_b: int) -> int:
    """Bit-count of (fp_a XOR fp_b) — number of differing bits."""
    x = fp_a ^ fp_b
    # Brian Kernighan's bit-counting trick
    count = 0
    while x:
        x &= x - 1
        count += 1
    return count


def is_near_duplicate(fp_a: int, fp_b: int, threshold: int = SIMHASH_THRESHOLD) -> bool:
    return hamming_distance(fp_a, fp_b) <= threshold