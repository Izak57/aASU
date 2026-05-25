from typing import Any, Self, Type, TypeVar, Generic, overload

from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.cursor import Cursor as PyMongoCursor


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
        return Collection(name, self, model=model, primary_key=primary_key)



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
             filters: dict[str, Any],
             *,
             limit: int | None = None,
             projection: dict[str, Any] | None = None) -> "Cursor[ColModelT]":
        cursor = Cursor(self, filters, limit=limit, projection=projection)
        return cursor


    def find_one(self, filters: dict[str, Any]) -> "ColModelT | None":
        cursor = self.find(filters, limit=1)
        return next(cursor, None)


    def get(self, id: Any) -> "ColModelT | None":
        return self.find_one({self.primary_key: id})



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
        self.current_cursor: PyMongoCursor | None = None


    def filter(self, filters: dict[str, Any]) -> Self:
        self.filters.update(filters)
        return self


    def limit(self, limit: int) -> Self:
        self.record_limit = limit
        return self


    def project(self, projection: dict[str, Any]) -> Self[ColModelT]:
        self.projection = projection
        return self


    def _build_cursor(self) -> PyMongoCursor:
        cursor = self.collection.collection.find(
            self.filters, projection=self.projection
        )

        if self.record_limit is not None:
            cursor = cursor.limit(self.record_limit)

        self.current_cursor = cursor
        return cursor
    

    def first(self) -> ColModelT | None:
        obj = next(iter(self), None)
        if obj is None:
            return None

        if self.collection.model is not None:
            assert issubclass(self.collection.model, BaseModel)
            return self.collection.model.model_validate(obj)
        else:
            return obj


    def all(self) -> list[ColModelT]:
        return list(iter(self))


    def __iter__(self):
        if self.current_cursor is None:
            self._build_cursor()

        return self


    def __next__(self) -> "ColModelT":
        if self.current_cursor is None:
            self._build_cursor()

        assert self.current_cursor is not None
        obj = next(self.current_cursor)

        if self.collection.model is not None:
            assert issubclass(self.collection.model, BaseModel)
            return self.collection.model.model_validate(obj)
        else:
            return obj
