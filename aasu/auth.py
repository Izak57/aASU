from typing import TypeVar, Generic, Any, Self
from secrets import token_urlsafe
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict
import jwt
from jwt import PyJWK
from jwt.types import Options as JwtOptions
from jwt.algorithms import AllowedPublicKeys, AllowedPrivateKeys, get_default_algorithms

from .exceptions import JwtDenied


__all__ = ["JwtAuthConfig", "JwtAuthenticator"]


AuthDataT = TypeVar("AuthDataT", bound=BaseModel)



class JwtAuthConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    encodekey: AllowedPrivateKeys | PyJWK | str | bytes | None = None
    """The key used to encode (private) a JWTs (prefer using .key if symetric)"""
    decodekey: AllowedPublicKeys | PyJWK | str | bytes | None = None
    """The key used to decode (public) a JWTs (prefer using .key if symetric)"""
    key: PyJWK | str | bytes | None = None # symetric only
    """The key used to both encode and decode JWTs (symetric)"""
    algorithms: list[str] | None = None
    """The list of supported algorithms during JWT decoding"""
    issuer: str | None = None
    """JWT issuer (iss key)"""
    audience: list[str] | None = None
    """JWT audience (aud key)"""
    expiration: timedelta | int | None = None # TODO: or timedelta
    """JWT expiration in seconds or as a timedelta (exp key)"""



class JwtAuthenticator(Generic[AuthDataT]):
    """Base class to create an authentification method
    with JSON Web Tokens.
    """

    def __init__(self, data: AuthDataT) -> None:
        self.data = data
        """The object that was in the JWT"""


    def __init_subclass__(cls, model: type[AuthDataT]) -> None:
        cls._auth_data_model = model
        """The model of the payload in the JWT"""


    def __repr__(self) -> str:
        return "<{} data={!r}>".format(
            self.__class__.__name__,
            self.data
        )


    @staticmethod
    def verify_jwt(token: str) -> None:
        """A checker function that verifies the JWT
        before its decoding"""
        ...


    @staticmethod
    def verify_data(data: dict[str, Any]) -> None:
        """A chercker function that verifies the data
        before its validation by the model"""
        ...


    @classmethod
    def generate(cls,
                 obj: AuthDataT,
                 config: JwtAuthConfig,
                 extra_data: dict[str, Any] | None = None) -> str:
        """Generates a JSON Web Token with the given data
        and configuration"""
        iat = datetime.now()
        tokeninfo = {
            "jti": token_urlsafe(6),
            "iat": int(iat.timestamp())
        }

        if config.issuer is not None:
            tokeninfo["iss"] = config.issuer

        if config.audience is not None:
            tokeninfo["aud"] = config.audience

        if config.expiration is not None:
            exptd = config.expiration \
                if isinstance(config.expiration, timedelta) \
                else timedelta(seconds=config.expiration)
            tokeninfo["exp"] = int((iat + exptd).timestamp())

        encodekey = config.encodekey or config.key
        assert encodekey, "There is not either encodekey or key, you need to put one lil bro"

        payload = tokeninfo | obj.model_dump(mode="json") | (extra_data or {})
        jwtoken = jwt.encode(payload, encodekey)
        return jwtoken


    @classmethod
    def load(cls,
             token: str,
             config: JwtAuthConfig,
             opts: JwtOptions | None = None) -> Self:
        """Loads a JSON Web Token and returns an auth
        with the object inside the JWT payload as .data"""
        algorithms = config.algorithms
        if not algorithms:
            algorithms = list(get_default_algorithms().keys())

        decodekey = config.decodekey or config.key
        assert decodekey, "There is not either decodekey or key, you need to put one lil bro"

        try:
            cls.verify_jwt(token)
            data = jwt.decode(
                token,
                decodekey,
                algorithms=algorithms,
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
