from typing import Any, Iterator, Self, Type, TypeVar, Generic, overload, cast

from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.cursor import Cursor as PyMongoCursor
from pymongo.command_cursor import CommandCursor as PyMongoCommandCursor


__all__ = [
    "Database", "Collection", "Cursor", "AggregateCursor",
    "ASC", "DESC"
]


ColModelT = TypeVar("ColModelT")
AggregateResultT = TypeVar("AggregateResultT")
ASC = 1
DESC = -1



class Database:

    def __init__(self,
                 uri: str,
                 db_name: str,
                 *,
                 mongo_client: MongoClient | None = None):
        """Initialize a database connection with a given
        MongoDB URL or client"""
        if mongo_client is not None:
            self.client = mongo_client
        else:
            self.client = MongoClient(uri)

        self.db = self.client[db_name]
        """The pymongo database instance (used in internal)"""
        self._collections: dict[str, Collection[Any]] = {}


    def __repr__(self) -> str:
        return "<{} ({} registered collections)>".format(
            self.__class__.__name__,
            len(self._collections)
        )


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
        """Creates a collection/table of data  following
        a given Pydantic Model"""
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
        """Initialize a collection of data from a database.
        Prefer using db.collection() function instead."""
        self.name = name
        self.database = database
        self.model = model
        self.primary_key = primary_key


    def __repr__(self) -> str:
        return "<{} name={!r} model={!r}>".format(
            self.__class__.__name__,
            self.name,
            self.model
        )


    @property
    def collection(self):
        """The pymongo collection instance (used in internal)"""
        return self.database.db[self.name]


    def insert(self, *objs: ColModelT | dict[str, Any]) -> None:
        """Insert one or many objects into the collection"""
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
             sort: list[tuple[str, int]] | None = None,
             skip: int | None = None,
             projection: dict[str, Any] | None = None) -> "Cursor[ColModelT]":
        """Finds objects in the collection.
        Actually creates a cursor"""
        cursor = Cursor(
            self, filters.copy(),
            limit=limit, projection=projection,
            skip_offset=skip or 0,
            sort_data=sort
        )
        return cursor


    def insert_or_update(self, obj: ColModelT | dict[str, Any]) -> None:
        """Insert or update a object into the collection.
        The object is updated if the primary key value already exists."""
        if isinstance(obj, BaseModel):
            dict_obj = obj.model_dump(mode="json")
        else:
            dict_obj = cast(dict[str, Any], obj)

        primarykey = dict_obj[self.primary_key]
        filters = {self.primary_key: primarykey}

        exists = self.count(filters) > 0

        if exists:
            self.update_one(filters, {"$set": dict_obj})
        else:
            self.insert(dict_obj)


    def update(self,
               filters: dict[str, Any] | str,
               update_data: dict[str, Any]) -> None:
        """Update objects in the collection that match the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        self.collection.update_many(ftrs, update_data)


    def update_one(self,
                   filters: dict[str, Any] | str,
                   update_data: dict[str, Any],
                   *,
                   sort: list[tuple[str, int]] | dict[str, int] | None = None) -> None:
        """Update a single object in the collection that matches the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        sortt = dict(sort) if isinstance(sort, list) else sort
        self.collection.update_one(ftrs, update_data, sort=sortt)


    @overload
    def aggregate(self, pipeline: list[dict[str, Any]]) -> "AggregateCursor[dict[str, Any]]":
        ...


    @overload
    def aggregate(self,
                  pipeline: list[dict[str, Any]],
                  result_type: Type[AggregateResultT]) -> "AggregateCursor[AggregateResultT]":
        ...


    def aggregate(self,
                  pipeline: list[dict[str, Any]],
                  result_type: Type[AggregateResultT] | None = None) -> "AggregateCursor":
        """Perform aggregation pieplines inside the collection"""
        cursor = AggregateCursor(self, pipeline, result_type=result_type)
        return cursor


    def find_one(self,
                 filters: dict[str, Any],
                 projection: dict[str, Any] | None = None) -> "ColModelT | None":
        """Returns the first object that matches the filters"""
        cursor = self.find(filters, limit=1, projection=projection)
        return next(cursor, None)


    def get(self, id: Any) -> "ColModelT | None":
        """Returns the object with the given primary key value"""
        return self.find_one({self.primary_key: id})


    def count(self, filters: dict[str, Any] = {}) -> int:
        """Returns the number of objects that match the filters"""
        return self.collection.count_documents(filters)


    def delete(self, filters: dict[str, Any] | str) -> None:
        """Delete objects in the collection that match the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        self.collection.delete_many(ftrs)


    def __delitem__(self, id: Any) -> None:
        self.delete(id)



class Cursor(Generic[ColModelT]):

    def __init__(self,
                 collection: Collection[ColModelT],
                 filters: dict[str, Any],
                 limit: int | None = None,
                 projection: dict[str, Any] | None = None,
                 skip_offset: int = 0,
                 sort_data: list[tuple[str, int]] | None = None):
        self.collection = collection
        self.filters = filters
        self.record_limit = limit
        self.projection = projection
        self.skip_offset = skip_offset
        self.current_cursor: PyMongoCursor | None = None
        self.sort_data = sort_data or []


    def __repr__(self) -> str:
        return "<DatabaseCursor collection={}".format(
            self.collection.name
        )


    def copy(self) -> "Cursor":
        return Cursor(
            collection=self.collection,
            filters=self.filters.copy(),
            limit=self.record_limit,
            projection=(self.projection or {}).copy(),
            skip_offset=self.skip_offset
        )


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


    def sort(self, *sort: tuple[str, int], **sortkw: int) -> Self:
        self.sort_data = list(sort) + list(sortkw.items())
        return self


    def _build_cursor(self) -> PyMongoCursor:
        cursor = self.collection.collection.find(
            self.filters, projection=self.projection
        )

        if self.record_limit is not None:
            cursor = cursor.limit(self.record_limit)

        if self.skip_offset > 0:
            cursor = cursor.skip(self.skip_offset)

        if self.sort_data:
            cursor = cursor.sort(self.sort_data)

        self.current_cursor = cursor
        return cursor


    def first(self) -> ColModelT | None:
        obj = next(iter(self), None)
        return obj


    def all(self) -> list[ColModelT]:
        return list(iter(self))


    def __iter__(self) -> Iterator[ColModelT]:
        cc = self._build_cursor()
        for obj in cc:
            yield self._deserialize(obj)


    def __next__(self) -> "ColModelT":
        if self.current_cursor is None:
            self._build_cursor()

        assert self.current_cursor is not None
        obj = next(self.current_cursor)
        return self._deserialize(obj)


    def _deserialize(self, obj: dict[str, Any]) -> ColModelT:
        if self.collection.model is not None:
            assert issubclass(self.collection.model, BaseModel)
            return self.collection.model.model_validate(obj)
        else:
            return obj # type: ignore



class AggregateCursor(Generic[AggregateResultT]):

    def __init__(self,
                 collection: Collection[ColModelT],
                 pipeline: list[dict[str, Any]],
                 result_type: Type[AggregateResultT] | None = None) -> None:
        self.collection = collection
        self.pipeline = pipeline
        self.result_type = result_type
        self.current_cursor: PyMongoCommandCursor | None = None


    def __repr__(self) -> str:
        return "<DatabaseAggregateCursor collection={}>".format(
            self.collection.name
        )


    def __iter__(self):
        if self.current_cursor is None:
            self._build_cursor()

        return self


    def __next__(self) -> AggregateResultT:
        if self.current_cursor is None:
            self._build_cursor()

        assert self.current_cursor is not None
        obj = next(self.current_cursor)

        if self.result_type and issubclass(self.result_type, BaseModel):
            return self.result_type.model_validate(obj)
        return obj


    def add_line(self, *pipeline: dict[str, Any]) -> Self:
        self.pipeline.extend(pipeline)
        return self


    def _build_cursor(self) -> PyMongoCommandCursor:
        cursor = self.collection.collection.aggregate(self.pipeline)
        self.current_cursor = cursor
        return cursor
