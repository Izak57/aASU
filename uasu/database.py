from typing import Any, Self

from pymongo import MongoClient
from pymongo.cursor import Cursor as PyMongoCursor



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



class Collection:

    def __init__(self, name: str, database: Database):
        self.name = name
        self.database = database
        

    @property
    def collection(self):
        return self.database.db[self.name]
    

    def find(self,
             filters: dict[str, Any],
             *,
             limit: int | None = None) -> "Cursor":
        cursor = Cursor(self, filters, limit=limit)
        return cursor
        



class Cursor:

    def __init__(self,
                 collection: Collection,
                 filters: dict[str, Any],
                 limit: int | None = None):
        self.collection = collection
        self.filters = filters
        self.limit_i = limit

    def filter(self, filters: dict[str, Any]) -> Self:
        self.filters.update(filters)
        return self
    
    def limit(self, limit: int) -> Self:
        self.limit_i = limit
        return self
