from typing import TypeVar, Generic, Any, Self
from secrets import token_urlsafe
from datetime import datetime

from pydantic import BaseModel
import jwt
from jwt import PyJWK
from jwt.types import Options as JwtOptions


AuthDataT = TypeVar("AuthDataT", bound=BaseModel)



class JwtAuthConfig(BaseModel):
    key: PyJWK
    issuer: str | None = None
    audience: list[str] | None = None
    expires_in: int | None = None



class JwtAuthenticator(Generic[AuthDataT]):

    def __init__(self, data: AuthDataT) -> None:
        self.data = data


    def __init_subclass__(cls, model: type[AuthDataT]) -> None:
        cls._auth_data_model = model


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
        # TODO: call .verify_jwt(token)
        data = jwt.decode(
            token,
            config.key,
            options=opts,
            issuer=config.issuer
        )

        # TODO: call .verify_data(data)
        authdata = cls._auth_data_model.model_validate(data, extra="ignore")
        authenti = cls(authdata)
        return authenti