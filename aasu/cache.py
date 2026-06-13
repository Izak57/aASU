from typing import TypeVar, Generic, Generator, Any, overload, cast
from datetime import datetime

from pydantic import BaseModel
from fastapi import FastAPI
from redis import Redis


__all__ = ["CacheDatabase", "CacheController"]


CacheControllerModelT = TypeVar("CacheControllerModelT")



class CacheDatabase:

    def __init__(self, rclient: Redis | None = None) -> None:
        if rclient:
            self.rclient = rclient
        """The Redis client"""
        self.app: FastAPI | None = None
        """The FastAPI application (not used)"""
        self._controllers: list[CacheController] = []


    def __repr__(self) -> str:
        return "<{} ({} registered controllers)>".format(
            self.__class__.__name__,
            len(self._controllers)
        )


    def set_redis_client(self, rclient: Redis) -> None:
        """Set the Redis client"""
        self.rclient = rclient


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
        """The database"""
        self.key = key
        """The prefix used to store objects"""
        self.model = model
        """The Pydantic model of the objects you want to cache"""
        self.default_expiration = default_expiration
        """A default expiration (in seconds) for every stored object"""


    def __repr__(self) -> str:
        return "<{} key={!r} model={!r}>".format(
            self.__class__.__name__,
            self.key,
            self.model
        )


    def __getitem__(self, key: str):
        return self.get(key)


    def __setitem__(self, key: str, value):
        self.set(key, value)


    def __delitem__(self, key: str) -> None:
        self.delete(key)


    def _deserialize(self, rawval: str | None) -> Any:
        if rawval is None:
            return None

        if self.model:
            obj = self.model.model_validate_json(rawval) # type: ignore
        else:
            obj = rawval

        return obj # type: ignore


    def _serialize_value(self, value: Any) -> str:
        if isinstance(value, BaseModel):
            valdata = value.model_dump_json()

        elif isinstance(value, str):
            valdata = value

        else:
            raise TypeError("value should either be a string, or a pydantic model instance")
        
        return valdata


    def set(self,
            key: str,
            value: CacheControllerModelT,
            expires_in: int | None | str = "default",
            *,
            expires_at: datetime | int | None = None,
            keep_ttl: bool = False) -> None:
        """Set an object into the collection"""
        if expires_at:
            expi = None

            if isinstance(expires_at, datetime):
                expires_at = int(expires_at.timestamp())

        elif keep_ttl:
            expi = None

        elif expires_in == "default":
            expi = self.default_expiration

        else:
            expi = expires_in

        expi = self.default_expiration if expires_in == "default" else expires_in
        expi = cast(int | None, expi)

        valdata = self._serialize_value(value)

        self.cdb.rclient.set(
            f"{self.key}:{key}", valdata,
            ex=expi, exat=expires_at, keepttl=keep_ttl
        )


    def get(self, key: str) -> CacheControllerModelT | None:
        """Get an object by its key from the collection"""
        rawval = self.cdb.rclient.get(f"{self.key}:{key}")
        return self._deserialize(rawval) # type: ignore


    def delete(self, key: str) -> None:
        """Delete an object by its key from the collection"""
        self.cdb.rclient.delete(f"{self.key}:{key}")


    remove = delete


    def pop(self, key: str) -> CacheControllerModelT | None:
        """Get an object then deletes it"""
        rawval = self.cdb.rclient.getdel(f"{self.key}:{key}")
        return self._deserialize(rawval) # type: ignore


    def getex(self,
              key: str,
              expires_in: int | None = None,
              *,
              expires_at: datetime | int | None = None,
              persist: bool = False):
        """Get an object then set an expiration"""
        rawval = self.cdb.rclient.getex(
            f"{self.key}:{key}",
            ex=expires_in,
            exat=expires_at,
            persist=persist
        )
        return self._deserialize(rawval) # type: ignore


    def getset(self,
               key: str,
               value: CacheControllerModelT) -> CacheControllerModelT | None:
        """Get an object then set its next value"""
        valdata = self._serialize_value(value)
        rawval = self.cdb.rclient.getset(f"{self.key}:{key}", valdata)
        return self._deserialize(rawval) # type: ignore


    def ttl(self, key: str) -> int | None:
        """Returns the time-to-live of an object"""
        return self.cdb.rclient.ttl(f"{self.key}:{key}") # type: ignore


    def scan(self, pattern: str = "*") -> Generator[str, None, None]:
        """Returns a list of all keys in the collection matching the pattern"""
        full_pattern = f"{self.key}:{pattern}"
        for key in self.cdb.rclient.scan_iter(full_pattern):
            yield key.decode("utf-8").split(":", 1)[1]


    def purge(self, batch_size: int = 500) -> None:
        """Clear all the collection"""
        keys = [f"{self.key}:{k}" for k in self.scan()]
        pipeline = self.cdb.rclient.pipeline()

        for i, key in enumerate(keys):
            pipeline.delete(key)

            if (i + 1) % batch_size == 0:
                pipeline.execute()
                pipeline = self.cdb.rclient.pipeline()

        pipeline.execute()
