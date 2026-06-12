import jwt
import time
import uuid
import requests
import logging
import os

from fastapi import Request
from functools import wraps
from typing import Optional, Union
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

REQUEST_VERIFY = False


class ElementoIdentityAccessManagementException(Exception):
    def __init__(self, message):
        self.message = message


class RealmAccess(BaseModel):
    roles: list[str]


class ResourceRoles(BaseModel):
    roles: list[str]


class AccessToken(BaseModel):
    """
    Class that represents the structure of a Keycloak access token
    """

    exp: int
    iat: int
    jti: str
    iss: str
    aud: Optional[Union[list[str], str]] = None
    sub: str
    typ: str
    azp: str
    sid: str
    acr: str
    allowed_origins: list[str] = []
    realm_access: RealmAccess
    # resource_access: dict[str, ResourceRoles]
    scope: str
    email_verified: bool
    elemento_role: str
    name: str
    client_uuid: str
    preferred_username: str
    given_name: str
    family_name: str
    email: str
    elemento_org: Optional[str] = None
    elemento_managed_members: Optional[list[str]] = []


class ElementoIdentityAccessManagement:
    """
    Class used to verify and validate access tokens received by Elemento Clients.

    Attributes:
        keycloak_url(str): url of Keycloak instance
        keycloak_realm(str): name of the Keycloak realm you want to refer to
        keycloak_target_client_id(str): target client for the token exchange
        jwks_cache_ttl(int): cache time to live (seconds) before refresh Keycloak pubkey
        get_local_ips_fun: function to get local IPs, if not passed the auth header is always requested
    """

    def __init__(
        self,
        keycloak_target_client_id: str = "portal-internal-client",
        keycloak_realm: str = "portal",
        jwks_cache_ttl: int = 300,
        get_local_ips_fun=None,
    ):

        env = os.getenv("ENV", "development")
        dev_url = os.getenv("DEV_PORTAL_URL", "https://beta.portal.elemento.cloud:9999/api/v2")
        prod_url = os.getenv("PROD_PORTAL_URL", "https://portal.elemento.cloud/api/v1")

        raw_url = dev_url if env in ["development", "local"] else prod_url

        base_url = raw_url.split("/api/")[0].rstrip("/")

        if env in ["development", "local"]:
            parsed = urlparse(base_url)
            self.keycloak_url = f"{parsed.scheme}://{parsed.hostname}:8444"
        else:
            self.keycloak_url = "https://elemento-portal.idp.cloud"

        logging.debug("keycloak URL: %s", self.keycloak_url)
        self.keycloak_target_client_id = keycloak_target_client_id
        self.keycloak_realm = keycloak_realm
        self.jwks_url = f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"
        self.jwks_cache_ttl = jwks_cache_ttl
        self._jwks_cache_iat = 0
        self._jwks_cache = None
        self.get_local_ips_fun = get_local_ips_fun

    def _get_jwks(self) -> str:
        current_time = time.time()
        if self._jwks_cache is None or current_time - self._jwks_cache_iat > self.jwks_cache_ttl:
            ##* cache update
            response = requests.get(self.jwks_url, timeout=10, verify=REQUEST_VERIFY)
            response.raise_for_status()
            self._jwks_cache = response.json()
            self._jwks_cache_iat = current_time

        return self._jwks_cache

    def _validate_token(self, token: str) -> AccessToken:
        try:
            expected_issuer = f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            expected_audience = ["account", self.keycloak_target_client_id]
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            jwks = self._get_jwks()
            jwk = next((key for key in jwks["keys"] if key["kid"] == kid), None)
            if not jwk:
                raise ElementoIdentityAccessManagementException(f"Key ID '{kid}' not found in JWKS")

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)  ##? convert JWK to RSA public key
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=expected_issuer,
                options={"verify_aud": False},
            )
            access_token = AccessToken(**payload)

            now = int(time.time())
            if now >= access_token.exp:
                raise ElementoIdentityAccessManagementException("Token has expired")
            elif now < access_token.iat:
                raise ElementoIdentityAccessManagementException("Token not yet valid (issued in the future)")

            return access_token

        except jwt.InvalidTokenError as e:
            raise ElementoIdentityAccessManagementException(f"JWT verification failed: {str(e)}")
        except ValidationError as e:
            raise ElementoIdentityAccessManagementException(f"Validation error: {str(e)}")
        except requests.RequestException as e:
            raise ElementoIdentityAccessManagementException(f"Failed to fetch JWKS: {str(e)}")

    def _client_authorization(self, access_token: AccessToken, client_scope: Union[list[str], str]) -> bool:
        allowed_scope = [
            uuid.UUID(u)
            for u in (
                access_token.elemento_managed_members + [access_token.client_uuid]
                if isinstance(access_token.elemento_managed_members, list)
                else [access_token.elemento_managed_members, access_token.client_uuid]
            )
        ]
        if isinstance(client_scope, list):
            return all(uuid.UUID(client_uuid) in allowed_scope for client_uuid in client_scope)
        else:
            return uuid.UUID(client_scope) in allowed_scope

    def check_identity_access(self, token: str, clients_scope: Union[list[str], str]) -> bool:
        """
        Method used to check if the issued token contains the requested client's scope.

        Attributes:
            token(str): access token
            clients_scope(Union[list[str], str])): list of uuids or single uuid (both cases as strings) to which authorization is requested
        """
        try:
            access_token = self._validate_token(token)
        except ElementoIdentityAccessManagementException:
            return False

        try:
            if not self._client_authorization(access_token, clients_scope):
                return False
        except ValueError:
            return False

        return True

    def validate_request(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            req: Request = kwargs.get("request")
            ##* Check if request is from the same host
            if self.get_local_ips_fun is not None:
                client_ip = req.client.host
                if client_ip in self.get_local_ips_fun():
                    return func(*args, **kwargs)

            ##* extract token
            auth_header = req.headers.get("Authorization")
            if auth_header is None or not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=400, content={"error": "Missing or invalid token"})

            try:
                encoded_token = auth_header.split(" ", 1)[1]
            except (AttributeError, ValueError):
                return JSONResponse(status_code=400, content={"error": "Invalid access token header format"})
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

            try:
                access_token = self._validate_token(encoded_token)
                kwargs["token"] = access_token
            except ElementoIdentityAccessManagementException as e:
                logging.error(str(e))
                return JSONResponse(status_code=401, content={"error": str(e)})

            client_uuid = req.headers.get("client_uuid")
            if client_uuid is None:
                return await func(*args, **kwargs)

            try:
                if not self._client_authorization(access_token, client_uuid):
                    ##? Using 403 as status code implies a block of the service (WIP)
                    return JSONResponse(status_code=403, content={"error": "Unauthorized"})
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "Invalid UUID format in access token or in payload"})

            return await func(*args, **kwargs)

        return wrapper

    def get_token_data(self, request: Request) -> AccessToken:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise ElementoIdentityAccessManagementException("Missing or invalid Authorization header")

        try:
            token = auth_header.split(" ", 1)[1]
            return self._validate_token(token)
        except (IndexError, AttributeError):
            raise ElementoIdentityAccessManagementException("Invalid token format")