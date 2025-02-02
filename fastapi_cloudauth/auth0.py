from typing import Any, Dict, Optional

import requests
from authlib.jose import JsonWebKey, jwk
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from starlette import status

from .base import ScopedAuth, UserInfoAuth
from .messages import NOT_VERIFIED
from .verification import JWKS as BaseJWKS
from .verification import ExtraVerifier


def get_issuer(domain: str) -> str:
    url = f"https://{domain}/.well-known/openid-configuration"
    openid_config = requests.get(url).json()
    return str(openid_config.get("issuer", ""))


class JWKS(BaseJWKS):
    def _construct(self, jwks: Dict[str, Any]) -> Dict[str, JsonWebKey]:
        return {_jwk["kid"]: jwk.loads(_jwk) for _jwk in jwks.get("keys", [])}


class Auth0(ScopedAuth):
    """
    Verify access token of auth0
    """

    user_info = None

    def __init__(
        self,
        domain: str,
        customAPI: str,
        issuer: Optional[str] = None,
        scope_key: Optional[str] = "permissions",
        auto_error: bool = True,
    ):
        url = f"https://{domain}/.well-known/jwks.json"
        jwks = JWKS(url=url)
        if issuer is None:
            issuer = get_issuer(domain)
        super().__init__(
            jwks,
            audience=customAPI,
            issuer=issuer,
            scope_key=scope_key,
            auto_error=auto_error,
            extra=Auth0ExtraVerifier(),
        )


class Auth0Claims(BaseModel):
    username: str = Field(alias="name")
    email: str = Field(None, alias="email")


class Auth0CurrentUser(UserInfoAuth):
    """
    Verify ID token and get user info of Auth0
    """

    user_info = Auth0Claims

    def __init__(
        self,
        domain: str,
        client_id: str,
        nonce: Optional[str] = None,
        issuer: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        url = f"https://{domain}/.well-known/jwks.json"
        jwks = JWKS(url=url)
        if issuer is None:
            issuer = get_issuer(domain)
        super().__init__(
            jwks,
            *args,
            user_info=self.user_info,
            audience=client_id,
            issuer=issuer,
            extra=Auth0ExtraVerifier(nonce=nonce),
            **kwargs,
        )


class Auth0ExtraVerifier(ExtraVerifier):
    def __init__(self, nonce: Optional[str] = None):
        self._nonce = nonce

    def __call__(self, claims: Dict[str, str], auto_error: bool = True) -> bool:
        # TODO: check the aud more

        # check the nonce
        try:
            nonce = claims["nonce"]
            if nonce != self._nonce:
                if auto_error:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail=NOT_VERIFIED
                    )
                return False
        except KeyError:
            pass
        return True
