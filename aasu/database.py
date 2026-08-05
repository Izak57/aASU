from typing import Any, AsyncIterator, Self, Type, TypeVar, Generic, overload, cast

from pydantic import BaseModel
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCursor,
    AsyncIOMotorCommandCursor,
)
from pymongo import (
    InsertOne as MongoInsertOne,
    UpdateOne as MongoUpdateOne,
    UpdateMany as MongoUpdateMany,
    ReplaceOne as MongoReplaceOne,
    DeleteOne as MongoDeleteOne,
    DeleteMany as MongoDeleteMany,
    ReturnDocument
)
from pymongo.results import BulkWriteResult


__all__ = [
    "Database", "Collection", "Cursor", "AggregateCursor",
    "BulkBubble",
    "ASC", "DESC"
]


ColModelT = TypeVar("ColModelT")
AggregateResultT = TypeVar("AggregateResultT")
ASC = 1
DESC = -1



class Database:

    def __init__(self,
                 uri: str | None,
                 db_name: str,
                 *,
                 mongo_client: AsyncIOMotorClient | None = None):
        """Initialize a database connection with a given
        MongoDB URL or client"""
        self.db_name = db_name

        if mongo_client:
            self.client = mongo_client

        elif uri:
            self.client = AsyncIOMotorClient(uri)

        else:
            raise ValueError("uri or mongo_client is required")

        """The motor database instance (used in internal)"""
        self._collections: dict[str, Collection[Any]] = {}


    def __repr__(self) -> str:
        return "<{} ({} registered collections)>".format(
            self.__class__.__name__,
            len(self._collections)
        )


    @property
    def db(self):
        """The motor database instance (used in internal)"""
        return self.client[self.db_name]


    def connect(self,
                uri: str | None,
                mongo_client: AsyncIOMotorClient | None = None) -> None:
        """Connect to a database with a given MongoDB URL or client"""
        if mongo_client:
            self.client = mongo_client
        elif uri:
            self.client = AsyncIOMotorClient(uri)


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
        """The motor collection instance (used in internal)"""
        return self.database.db[self.name]


    async def insert(self, *objs: ColModelT | dict[str, Any]) -> None:
        """Insert one or many objects into the collection"""
        dict_objs = []
        for obj in objs:
            if isinstance(obj, BaseModel):
                dict_objs.append(obj.model_dump(mode="python"))
            else:
                dict_objs.append(obj)

        await self.collection.insert_many(dict_objs)


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


    async def insert_or_update(self, obj: ColModelT | dict[str, Any]) -> None:
        """Insert or update a object into the collection.
        The object is updated if the primary key value already exists."""
        if isinstance(obj, BaseModel):
            dict_obj = obj.model_dump(mode="python")
        else:
            dict_obj = cast(dict[str, Any], obj)

        primarykey = dict_obj[self.primary_key]
        filters = {self.primary_key: primarykey}

        exists = await self.count(filters) > 0

        if exists:
            await self.update_one(filters, {"$set": dict_obj})
        else:
            await self.insert(dict_obj)


    async def update(self,
                     filters: dict[str, Any] | str,
                     update_data: dict[str, Any]) -> None:
        """Update objects in the collection that match the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        await self.collection.update_many(ftrs, update_data)


    async def update_one(self,
                         filters: dict[str, Any] | str,
                         update_data: dict[str, Any],
                         *,
                         sort: list[tuple[str, int]] | dict[str, int] | None = None) -> None:
        """Update a single object in the collection that matches the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        sortt = dict(sort) if isinstance(sort, list) else sort
        await self.collection.update_one(ftrs, update_data, sort=sortt)


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


    async def find_one(self,
                       filters: dict[str, Any],
                       projection: dict[str, Any] | None = None) -> "ColModelT | None":
        """Returns the first object that matches the filters"""
        cursor = self.find(filters, limit=1, projection=projection)
        return await cursor.first()


    async def get(self, id: Any) -> "ColModelT | None":
        """Returns the object with the given primary key value"""
        return await self.find_one({self.primary_key: id})


    async def count(self, filters: dict[str, Any] = {}) -> int:
        """Returns the number of objects that match the filters"""
        return await self.collection.count_documents(filters)


    async def delete(self, filters: dict[str, Any] | str) -> None:
        """Delete objects in the collection that match the filters
        The filters can be a dict of filters or a primary key value"""
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        await self.collection.delete_many(ftrs)


    def bulk(self) -> "BulkBubble":
        """Returns a BulkBubble to queue and execute several write
        operations in a single round-trip:

            async with collection.bulk() as bubble:
                bubble.insert_one(obj)
                bubble.update_one(filters, {"$set": {...}})
                bubble.delete_one(id)
        """
        return BulkBubble(self)


    async def find_one_and_update(
        self,
        filters: dict[str, Any] | str,
        update_data: dict[str, Any],
        *,
        upsert: bool = False,
        return_after: bool = True,
    ) -> ColModelT | None:
        ftrs = filters if isinstance(filters, dict) else {self.primary_key: filters}
        doc = await self.collection.find_one_and_update(
            ftrs, update_data, upsert=upsert,
            return_document=ReturnDocument.AFTER if return_after else ReturnDocument.BEFORE,
        )
        return self._deserialize_or_none(doc)


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
            skip_offset=self.skip_offset,
            sort_data=self.sort_data.copy()
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


    def _build_cursor(self) -> AsyncIOMotorCursor:
        cursor = self.collection.collection.find(
            self.filters, projection=self.projection
        )

        if self.record_limit is not None:
            cursor = cursor.limit(self.record_limit)

        if self.skip_offset > 0:
            cursor = cursor.skip(self.skip_offset)

        if self.sort_data:
            cursor = cursor.sort(self.sort_data)

        return cursor


    async def first(self) -> ColModelT | None:
        async for obj in self:
            return obj
        return None


    async def all(self) -> list[ColModelT]:
        cursor = self._build_cursor()
        docs = await cursor.to_list(length=None)
        return [self._deserialize(obj) for obj in docs]


    async def __aiter__(self) -> AsyncIterator[ColModelT]:
        cursor = self._build_cursor()
        async for obj in cursor:
            yield self._deserialize(obj)


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


    def __repr__(self) -> str:
        return "<DatabaseAggregateCursor collection={}>".format(
            self.collection.name
        )


    async def __aiter__(self) -> AsyncIterator[AggregateResultT]:
        cursor = self._build_cursor()
        async for obj in cursor:
            yield self._deserialize(obj)


    async def first(self) -> AggregateResultT | None:
        async for obj in self:
            return obj
        return None


    async def all(self) -> list[AggregateResultT]:
        return [obj async for obj in self]


    def add_line(self, *pipeline: dict[str, Any]) -> Self:
        self.pipeline.extend(pipeline)
        return self


    def _build_cursor(self) -> AsyncIOMotorCommandCursor:
        return self.collection.collection.aggregate(self.pipeline)


    def _deserialize(self, obj: dict[str, Any]) -> AggregateResultT:
        if self.result_type and issubclass(self.result_type, BaseModel):
            return self.result_type.model_validate(obj)
        return obj # type: ignore


class BulkBubble:

    def __init__(self, collection: "Collection") -> None:
        """Queues write operations to execute them all in a single
        round-trip when the `async with` block exits.
        Prefer using collection.bulk() instead."""
        self.collection = collection
        self.operations: list[Any] = []
        self.result: BulkWriteResult | None = None


    def __repr__(self) -> str:
        return "<BulkBubble collection={!r} operations={}>".format(
            self.collection.name, len(self.operations)
        )


    def _filters(self, filters: dict[str, Any] | str) -> dict[str, Any]:
        return filters if isinstance(filters, dict) else {self.collection.primary_key: filters}


    def _dump(self, obj: Any | dict[str, Any]) -> dict[str, Any]:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="python")
        return obj


    def insert_one(self, obj: Any | dict[str, Any]) -> Self:
        """Queue an insert of a single object"""
        self.operations.append(MongoInsertOne(self._dump(obj)))
        return self


    def insert_many(self, *objs: Any | dict[str, Any]) -> Self:
        """Queue inserts of many objects"""
        self.operations.extend(MongoInsertOne(self._dump(obj)) for obj in objs)
        return self


    def update_one(self,
                    filters: dict[str, Any] | str,
                    update_data: dict[str, Any]) -> Self:
        """Queue an update of a single object matching the filters.
        The filters can be a dict of filters or a primary key value"""
        self.operations.append(MongoUpdateOne(self._filters(filters), update_data))
        return self


    def update_many(self,
                     filters: dict[str, Any] | str,
                     update_data: dict[str, Any]) -> Self:
        """Queue an update of every object matching the filters"""
        self.operations.append(MongoUpdateMany(self._filters(filters), update_data))
        return self


    def replace_one(self,
                     filters: dict[str, Any] | str,
                     obj: Any | dict[str, Any]) -> Self:
        """Queue a full replace of a single object matching the filters"""
        self.operations.append(MongoReplaceOne(self._filters(filters), self._dump(obj)))
        return self


    def delete_one(self, filters: dict[str, Any] | str) -> Self:
        """Queue a delete of a single object matching the filters"""
        self.operations.append(MongoDeleteOne(self._filters(filters)))
        return self


    def delete_many(self, filters: dict[str, Any] | str) -> Self:
        """Queue a delete of every object matching the filters"""
        self.operations.append(MongoDeleteMany(self._filters(filters)))
        return self


    async def execute(self) -> BulkWriteResult | None:
        """Executes all queued operations in a single bulk_write call.
        Called automatically when leaving the `async with` block."""
        if not self.operations:
            return None

        self.result = await self.collection.collection.bulk_write(self.operations)
        return self.result


    async def __aenter__(self) -> Self:
        return self


    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Don't execute if an exception was raised inside the block,
        # so a partially-built bulk doesn't get sent by accident.
        if exc_type is None:
            await self.execute()
