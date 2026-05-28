from typing import TypeVar, Generic, Any, Self
from secrets import token_urlsafe
from datetime import datetime

from pydantic import BaseModel, ConfigDict
import jwt
from jwt import PyJWK
from jwt.types import Options as JwtOptions
from jwt.algorithms import AllowedPublicKeys

from .exceptions import JwtDenied


__all__ = ["JwtAuthConfig", "JwtAuthenticator"]


AuthDataT = TypeVar("AuthDataT", bound=BaseModel)



class JwtAuthConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    key: AllowedPublicKeys | PyJWK | str | bytes
    issuer: str | None = None
    audience: list[str] | None = None
    expires_in: int | None = None



class JwtAuthenticator(Generic[AuthDataT]):

    def __init__(self, data: AuthDataT) -> None:
        self.data = data


    def __init_subclass__(cls, model: type[AuthDataT]) -> None:
        cls._auth_data_model = model


    def __repr__(self) -> str:
        return "<{} data={!r}>".format(
            self.__class__.__name__,
            self.data
        )


    @staticmethod
    def verify_jwt(token: str) -> None:
        ...


    @staticmethod
    def verify_data(data: dict[str, Any]) -> None:
        ...


    @classmethod
    def generate(cls,
                 obj: AuthDataT,
                 config: JwtAuthConfig,
                 extra_data: dict[str, Any] | None = None) -> str:
        tokeninfo = {
            "jti": token_urlsafe(6),
            "iat": int(datetime.now().timestamp())
        }

        payload = tokeninfo | obj.model_dump(mode="json") | (extra_data or {})
        jwtoken = jwt.encode(payload, config.key)
        return jwtoken


    @classmethod
    def load(cls,
             token: str,
             config: JwtAuthConfig,
             opts: JwtOptions | None = None) -> Self:
        try:
            cls.verify_jwt(token)
            data = jwt.decode(
                token,
                config.key,
                options=opts,
                issuer=config.issuer
            )
        except jwt.PyJWTError as e:
            raise JwtDenied("Failed to verify JWT") from e

        try:
            cls.verify_data(data)
            authdata = cls._auth_data_model.model_validate(data, extra="ignore")
        except Exception as e:
            raise JwtDenied("The data from the given JWT is invalid") from e

        authenti = cls(authdata)
        return authenti
