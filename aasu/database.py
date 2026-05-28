from typing import Any, Self, Type, TypeVar, Generic, overload

from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.cursor import Cursor as PyMongoCursor
from pymongo.command_cursor import CommandCursor as PyMongoCommandCursor
from fastapi import Depends


__all__ = ["Database", "Collection", "Cursor", "AggregateCursor"]


ColModelT = TypeVar("ColModelT")



class Database:
    """Manages a MongoDB connection and provides access to Collection instances."""

    def __init__(self,
                 uri: str,
                 db_name: str,
                 *,
                 mongo_client: MongoClient | None = None):
        """Initialize the database, creating a MongoClient from the URI unless one is provided."""
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
        """Return (or create) a Collection by name, optionally bound to a Pydantic model."""
        if name in self._collections:
            return self._collections[name]

        col = Collection(name, self, model=model, primary_key=primary_key)
        self._collections[name] = col
        return col
    

    def __getitem__(self, name: str) -> "Collection":
        """Return a Collection by name using subscript notation."""
        return self.collection(name)



class Collection(Generic[ColModelT]):
    """Represents a MongoDB collection with optional Pydantic model validation."""

    def __init__(self, 
                 name: str,
                 database: Database,
                 model: Type[ColModelT] | None = None,
                 *,
                 primary_key: str = "id"):
        """Initialize the collection with its name, parent database, optional model, and primary key."""
        self.name = name
        self.database = database
        self.model = model
        self.primary_key = primary_key

    @property
    def collection(self):
        """The underlying PyMongo collection object."""
        return self.database.db[self.name]


    def insert(self, *objs: ColModelT | dict[str, Any]) -> None:
        """Insert one or more objects into the collection."""
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
        """Return a Cursor for documents matching the given filters."""
        cursor = Cursor(self, filters.copy(), limit=limit, projection=projection)
        return cursor


    def aggregate(self, pipeline: list[dict[str, Any]]) -> AggregateCursor:
        """Return an AggregateCursor for the given aggregation pipeline."""
        cursor = AggregateCursor(self, pipeline)
        return cursor


    def find_one(self, filters: dict[str, Any]) -> "ColModelT | None":
        """Return the first document matching the given filters, or None."""
        cursor = self.find(filters, limit=1)
        return next(cursor, None)


    def get(self, id: Any) -> "ColModelT | None":
        """Return the document with the given primary key value, or None."""
        return self.find_one({self.primary_key: id})



class Cursor(Generic[ColModelT]):
    """A lazy, chainable cursor for iterating over MongoDB query results."""

    def __init__(self,
                 collection: Collection[ColModelT],
                 filters: dict[str, Any],
                 limit: int | None = None,
                 projection: dict[str, Any] | None = None,
                 skip_offset: int = 0):
        """Initialize the cursor with a collection, filters, and optional limit, projection, and skip offset."""
        self.collection = collection
        self.filters = filters
        self.record_limit = limit
        self.projection = projection
        self.skip_offset = skip_offset
        self.current_cursor: PyMongoCursor | None = None
    

    def copy(self) -> "Cursor":
        """Return a new Cursor with the same settings as this one."""
        return Cursor(
            collection=self.collection,
            filters=self.filters.copy(),
            limit=self.record_limit,
            projection=(self.projection or {}).copy(),
            skip_offset=self.skip_offset
        )


    def filter(self, filters: dict[str, Any]) -> Self:
        """Merge additional filters into the cursor and return self."""
        self.filters.update(filters)
        return self


    def limit(self, limit: int) -> Self:
        """Set the maximum number of results to return and return self."""
        self.record_limit = limit
        return self
    

    def skip(self, skip: int) -> Self:
        """Set the number of results to skip and return self."""
        self.skip_offset = skip
        return self


    def project(self, projection: dict[str, Any]) -> Self:
        """Set the projection (field selection) for the query and return self."""
        self.projection = projection
        return self


    def _build_cursor(self) -> PyMongoCursor:
        """Build and cache the underlying PyMongo cursor based on current settings."""
        cursor = self.collection.collection.find(
            self.filters, projection=self.projection
        )

        if self.record_limit is not None:
            cursor = cursor.limit(self.record_limit)

        if self.skip_offset > 0:
            cursor = cursor.skip(self.skip_offset)

        self.current_cursor = cursor
        return cursor


    def first(self) -> ColModelT | None:
        """Return the first result, or None if there are no results."""
        obj = next(iter(self), None)
        return obj


    def all(self) -> list[ColModelT]:
        """Return all results as a list."""
        return list(iter(self))


    def __iter__(self):
        """Build the underlying cursor if needed and return self as the iterator."""
        if self.current_cursor is None:
            self._build_cursor()

        return self


    def __next__(self) -> "ColModelT":
        """Return the next deserialized result from the cursor."""
        if self.current_cursor is None:
            self._build_cursor()

        assert self.current_cursor is not None
        obj = next(self.current_cursor)
        return self._deserialize(obj)


    def _deserialize(self, obj: dict[str, Any]) -> ColModelT:
        """Deserialize a raw MongoDB document into the collection's model, if set."""
        if self.collection.model is not None:
            assert issubclass(self.collection.model, BaseModel)
            return self.collection.model.model_validate(obj)
        else:
            return obj # type: ignore



class AggregateCursor:
    """A cursor for iterating over MongoDB aggregation pipeline results."""

    def __init__(self,
                 collection: Collection[ColModelT],
                 pipeline: list[dict[str, Any]]) -> None:
        """Initialize the aggregate cursor with a collection and aggregation pipeline."""
        self.collection = collection
        self.pipeline = pipeline
        self.current_cursor: PyMongoCommandCursor | None = None


    def __iter__(self):
        """Build the underlying cursor if needed and return self as the iterator."""
        if self.current_cursor is None:
            self._build_cursor()

        return self


    def __next__(self):
        """Return the next raw document from the aggregation cursor."""
        if self.current_cursor is None:
            self._build_cursor()

        assert self.current_cursor is not None
        obj = next(self.current_cursor)
        return obj


    def add_line(self, *pipeline: dict[str, Any]) -> Self:
        """Append one or more stages to the aggregation pipeline and return self."""
        self.pipeline.extend(pipeline)
        return self


    def _build_cursor(self) -> PyMongoCommandCursor:
        """Build and cache the underlying PyMongo aggregation cursor."""
        cursor = self.collection.collection.aggregate(self.pipeline)
        self.current_cursor = cursor
        return cursor
