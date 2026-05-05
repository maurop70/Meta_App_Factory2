import jwt
import datetime
from pathlib import Path

# Paths to the RS256 keys (Module 0 is the sole owner of the Private Key)
KEYS_DIR = Path(__file__).parent.parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "public_key.pem"

class MintingEngine:
    def __init__(self):
        with open(PRIVATE_KEY_PATH, "rb") as key_file:
            self.private_key = key_file.read()
            
        with open(PUBLIC_KEY_PATH, "rb") as key_file:
            self.public_key = key_file.read()

    def mint_access_token(self, data: dict):
        """Generates a short-lived RS256 signed access token (15m)."""
        import uuid
        to_encode = data.copy()
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
        encoded_jwt = jwt.encode(to_encode, self.private_key, algorithm="RS256")
        return encoded_jwt

    def mint_refresh_token(self, data: dict):
        """Generates a long-lived RS256 signed refresh token (7 days)."""
        import uuid
        to_encode = data.copy()
        expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        to_encode.update({"exp": expire, "jti": str(uuid.uuid4()), "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.private_key, algorithm="RS256")
        return encoded_jwt

    def verify_token(self, token: str):
        """Verifies a token using the public key."""
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["RS256"])
            return payload
        except jwt.PyJWTError as e:
            return None

# Singleton instance for the Gateway
minting_engine = MintingEngine()
