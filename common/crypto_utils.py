import base64
import json
from pathlib import Path
from typing import Any, Dict, List

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_key(password: bytes, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password)


def decrypt_payload(payload: Dict[str, Any], password: str, iterations: int) -> bytes:
    salt = base64.b64decode(payload["s"])
    nonce = base64.b64decode(payload["n"])
    ciphertext = base64.b64decode(payload["ct"])

    key = derive_key(password.encode("utf-8"), salt, iterations)
    aesgcm = AESGCM(key)

    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise RuntimeError("Decryption failed (InvalidTag)")


def normalize_cookies(cookies: List[Dict[str, Any]]) -> None:
    for c in cookies:
        if "partitionKey" in c:
            p_key = c["partitionKey"]
            if isinstance(p_key, dict):
                if "topLevelSite" in p_key and isinstance(p_key["topLevelSite"], str):
                    c["partitionKey"] = p_key["topLevelSite"]
                else:
                    del c["partitionKey"]
            elif not isinstance(p_key, str):
                del c["partitionKey"]

        if "sameSite" in c:
            val = str(c["sameSite"]).lower()
            if val in ["no_restriction", "none", "unspecified", "null"]:
                c["sameSite"] = "None"
            elif val == "lax":
                c["sameSite"] = "Lax"
            elif val == "strict":
                c["sameSite"] = "Strict"
            else:
                c["sameSite"] = "Lax"


def load_cookies(file_path: Path, password: str, iterations: int) -> List[Dict[str, Any]]:
    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plaintext = decrypt_payload(payload, password, iterations)
    cookies = json.loads(plaintext.decode("utf-8"))
    normalize_cookies(cookies)
    return cookies