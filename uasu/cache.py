from typing import TypeVar, Generic, overload, cast
from datetime import datetime

from pydantic import BaseModel
from fastapi import FastAPI, Request
from redis import Redis


CacheControllerModelT = TypeVar("CacheControllerModelT")



class CacheDatabase:

    def __init__(self, rclient: Redis) -> None:
        self.rclient = rclient
        self.app: FastAPI | None = None
        self._controllers: list[CacheController] = []


    @overload
    def cacher(self,
               key: str,
               model: type[CacheControllerModelT],
               *,
               default_expiration: int | None = None) -> "CacheController[CacheControllerModelT]":
        ...

    @overload
    def cacher(self,
               key: str,
               model: None = None,
               *,
               default_expiration: int | None = None) -> "CacheController[str]":
        ...

    def cacher(self,
               key: str,
               model = None,
               *,
               default_expiration: int | None = None):
        controller = CacheController(self, key, model=model, default_expiration=default_expiration)
        self._controllers.append(controller)
        return controller




class CacheController(Generic[CacheControllerModelT]):

    def __init__(self,
                 cdb: CacheDatabase,
                 key: str,
                 *,
                 model: CacheControllerModelT | None = None,
                 default_expiration: int | None = None) -> None:
        self.cdb = cdb
        self.key = key
        self.model = model
        self.default_expiration = default_expiration


    def __getitem__(self, key: str):
        return self.get(key)


    def __setitem__(self, key: str, value):
        self.set(key, value)


    def set(self,
            key: str,
            value: CacheControllerModelT,
            expires_in: int | None | str = "default",
            expires_at: datetime | int | None = None) -> None:
        if expires_at:
            expi = None

            if isinstance(expires_at, datetime):
                expires_at = int(expires_at.timestamp())

        elif expires_in == "default":
            expi = self.default_expiration
        
        else:
            expi = expires_in

        expi = self.default_expiration if expires_in == "default" else expires_in
        expi = cast(int | None, expi)

        if isinstance(value, BaseModel):
            valdata = value.model_dump_json()

        elif isinstance(value, str):
            valdata = value

        else:
            raise TypeError("value should either be a string, or a pydantic model instance")

        self.cdb.rclient.set(f"{self.key}:{key}", valdata, ex=expi, exat=expires_at)


    def get(self, key: str) -> CacheControllerModelT | None:
        rawval = self.cdb.rclient.get(f"{self.key}:{key}")

        if rawval is None:
            return None

        if self.model:
            obj = self.model.model_validate_json(rawval) # type: ignore
        else:
            obj = rawval

        return obj # type: ignore


    def ttl(self, key: str) -> int | None:
        return self.cdb.rclient.ttl(f"{self.key}:{key}") # type: ignore
