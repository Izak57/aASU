from typing import Any, Self, Type, TypeVar, Generic, overload

from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.cursor import Cursor as PyMongoCursor
from pymongo.command_cursor import CommandCursor as PyMongoCommandCursor


ColModelT = TypeVar("ColModelT")



class Database:

    def __init__(self,
                 uri: str,
                 db_name: str,
                 *,
                 mongo_client: MongoClient | None = None):
        if mongo_client is not None:
            self.client = mongo_client
        else:
            self.client = MongoClient(uri)

        self.db = self.client[db_name]
        self._collections: dict[str, Collection[Any]] = {}


    @overload
    def collection(
        self,
        name: str,
        model: Type[ColModelT],
        *,
        primary_key: str = "id"
    ) -> "Collection[ColModelT]":
        ...

    @overload
    def collection(
        self,
        name: str,
        model: None = None,
        *,
        primary_key: str = "id"
    ) -> "Collection[dict[str, Any]]":
        ...


    def collection(self,
                   name: str,
                   model: Type[ColModelT] | None = None,
                   *,
                   primary_key: str = "id") -> "Collection[ColModelT]":
        if name in self._collections:
            return self._collections[name]

        col = Collection(name, self, model=model, primary_key=primary_key)
        self._collections[name] = col
        return col
    

    def __getitem__(self, name: str) -> "Collection":
        return self.collection(name)



class Collection(Generic[ColModelT]):

    def __init__(self, 
                 name: str,
                 database: Database,
                 model: Type[ColModelT] | None = None,
                 *,
                 primary_key: str = "id"):
        self.name = name
        self.database = database
        self.model = model
        self.primary_key = primary_key

    @property
    def collection(self):
        return self.database.db[self.name]


    def insert(self, *objs: ColModelT | dict[str, Any]) -> None:
        dict_objs = []
        for obj in objs:
            if isinstance(obj, BaseModel):
                dict_objs.append(obj.model_dump(mode="json"))
            else:
                dict_objs.append(obj)

        self.collection.insert_many(dict_objs)


    def find(self,
             filters: dict[str, Any] = {},
             *,
             limit: int | None = None,
             projection: dict[str, Any] | None = None) -> "Cursor[ColModelT]":
        cursor = Cursor(self, filters.copy(), limit=limit, projection=projection)
        return cursor


    def find_one(self, filters: dict[str, Any]) -> "ColModelT | None":
        cursor = self.find(filters, limit=1)
        return next(iter(cursor), None)


    def get(self, id: Any) -> "ColModelT | None":
        return self.find_one({self.primary_key: id})


    def aggregate(self, pipeline: list[dict[str, Any]]) -> "AggregateCursor[ColModelT]":
        return AggregateCursor(self, pipeline)


    def deserialize(self, obj: dict[str, Any]) -> ColModelT:
        if self.model is not None:
            assert issubclass(self.model, BaseModel)
            return self.model.model_validate(obj)
        else:
            return obj # type: ignore



class Cursor(Generic[ColModelT]):

    def __init__(self,
                 collection: Collection[ColModelT],
                 filters: dict[str, Any],
                 limit: int | None = None,
                 projection: dict[str, Any] | None = None):
        self.collection = collection
        self.filters = filters
        self.record_limit = limit
        self.projection = projection
        self.skip_offset = 0


    def filter(self, filters: dict[str, Any]) -> Self:
        self.filters.update(filters)
        return self


    def limit(self, limit: int) -> Self:
        self.record_limit = limit
        return self
    

    def skip(self, skip: int) -> Self:
        self.skip_offset = skip
        return self


    def project(self, projection: dict[str, Any]) -> Self:
        self.projection = projection
        return self


    def _build_cursor(self) -> PyMongoCursor:
        cursor = self.collection.collection.find(
            self.filters, projection=self.projection
        )

        if self.record_limit is not None:
            cursor = cursor.limit(self.record_limit)

        if self.skip_offset > 0:
            cursor = cursor.skip(self.skip_offset)

        return cursor


    def first(self) -> ColModelT | None:
        obj = next(iter(self), None)
        return obj


    def all(self) -> list[ColModelT]:
        return list(iter(self))


    def __iter__(self):
        current_cursor = self._build_cursor()
        for obj in current_cursor:
            yield self._deserialize(obj)


    def _deserialize(self, obj: dict[str, Any]) -> ColModelT:
        return self.collection.deserialize(obj)



class AggregateCursor(Generic[ColModelT]):

    def __init__(self,
                 collection: Collection[ColModelT],
                 pipeline: list[dict[str, Any]]):
        self.collection = collection
        self.pipeline = pipeline


    def _build_cursor(self) -> PyMongoCommandCursor:
        return self.collection.collection.aggregate(self.pipeline)


    def first(self) -> ColModelT | None:
        obj = next(iter(self), None)
        return obj


    def all(self) -> list[ColModelT]:
        return list(iter(self))


    def __iter__(self):
        current_cursor = self._build_cursor()
        for obj in current_cursor:
            yield self._deserialize(obj)


    def _deserialize(self, obj: dict[str, Any]) -> ColModelT:
        return self.collection.deserialize(obj)
