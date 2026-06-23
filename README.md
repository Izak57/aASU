# aASU - All-in-One API Services and Utils

A comprehensive Python library providing utilities for building API services with FastAPI, async MongoDB integration (via [Motor](https://motor.readthedocs.io/)), Redis caching, and JWT authentication.

## Installation

```bash
pip install aasu
```

## Features

- **APIModel**: Pydantic-based models with JSON serialization
- **Database & Collection**: Async MongoDB integration with type-safe queries
- **Caching**: Redis-backed caching with automatic expiration
- **JWT Authentication**: Token-based authentication with customizable claims
- **FastAPI Integration**: Built-in response serialization for FastAPI

---

## Quick Start

```python
from aasu import APIModel, Database, CacheDatabase, JwtAuthConfig, JwtAuthenticator
from fastapi import FastAPI
from redis import Redis

# Initialize services
app = FastAPI()
db = Database("mongodb://localhost:27017", "mydb")
cache_db = CacheDatabase(Redis.from_url("redis://localhost"))
```

> **Note**: Database operations are **asynchronous** (powered by Motor). Methods that
> hit MongoDB — `insert`, `find_one`, `get`, `count`, `update`, `delete`, … — return
> coroutines and must be `await`ed inside an `async` function. Cursors are async
> iterators, so use `async for` (and `await cursor.all()` / `await cursor.first()`).

---

## Feature Documentation

### 1. APIModel - Pydantic-Based API Models

**Purpose**: Create API models with automatic JSON serialization compatible with FastAPI.

**Description**: `APIModel` extends Pydantic's `BaseModel` with built-in JSON serialization methods, making it ideal for API responses and request bodies.

#### Example

```python
from aasu import APIModel, apiserialize
from pydantic import Field

class User(APIModel):
    id: int
    name: str
    email: str
    age: int = Field(default=0)

# Create an instance
user = User(id=1, name="John Doe", email="john@example.com")

# Serialize to JSON-compatible dict
user_dict = user.apiserialize()
# Output: {'id': 1, 'name': 'John Doe', 'email': 'john@example.com', 'age': 0}

# Alternative: use the standalone function
user_dict = apiserialize(user)
```

#### Key Methods

- `apiserialize(privacy: str | None = None)`: Converts the model to a JSON-compatible dictionary
- `apiserialize(obj, privacy=None)`: Standalone function for serializing any Pydantic model

---

### 2. Database and Collection - MongoDB Integration

**Purpose**: Type-safe MongoDB database operations with automatic model validation.

**Description**: `Database` manages MongoDB connections and collections, while `Collection` provides async CRUD operations with automatic serialization/deserialization of Pydantic models. Document-touching methods are coroutines and must be awaited; `find()` and `aggregate()` return cursors synchronously (they only run when iterated/awaited).

#### Example

```python
from aasu import Database, APIModel

class Product(APIModel):
    id: str
    name: str
    price: float
    stock: int

# Initialize database
db = Database("mongodb://localhost:27017", "store_db")

# Get or create a collection with type hints
products_col = db.collection("products", Product, primary_key="id")

async def main():
    # Insert documents
    product1 = Product(id="P001", name="Laptop", price=999.99, stock=10)
    product2 = Product(id="P002", name="Mouse", price=29.99, stock=50)
    await products_col.insert(product1, product2)

    # Also insert raw dictionaries
    await products_col.insert({"id": "P003", "name": "Keyboard", "price": 79.99, "stock": 30})

    # Insert or update by primary key
    await products_col.insert_or_update({"id": "P001", "name": "Laptop Pro", "price": 1299.99, "stock": 5})

    # Get single document by ID
    laptop = await products_col.get("P001")
    # Returns: Product(id='P001', name='Laptop Pro', price=1299.99, stock=5)

    # Find with filters (find() builds the cursor, .all() runs the query)
    expensive = products_col.find({"price": {"$gt": 100}})
    results = await expensive.all()  # Get all results

    # Get first result
    first = await products_col.find({"stock": {"$gt": 0}}).first()

    # Count, update and delete
    in_stock = await products_col.count({"stock": {"$gt": 0}})
    await products_col.update({"price": {"$lt": 50}}, {"$inc": {"stock": 100}})
    await products_col.delete("P002")  # by primary key, or pass a filter dict
```

#### Collection Methods

All methods below are coroutines (use `await`) **except** `find` and `aggregate`, which return a cursor synchronously.

- `insert(*objs)`: Insert one or more documents (Pydantic models or dicts)
- `insert_or_update(obj)`: Insert, or update in place if the primary key already exists
- `find(filters, *, limit=None, sort=None, skip=None, projection=None)`: Build a `Cursor` (not a coroutine)
- `find_one(filters, projection=None)`: Get first document matching filters
- `get(id)`: Get document by primary key
- `count(filters={})`: Count documents matching filters
- `update(filters, update_data)`: Update every document matching filters
- `update_one(filters, update_data, *, sort=None)`: Update a single matching document
- `delete(filters)`: Delete documents matching a filter dict or a primary key value
- `aggregate(pipeline, result_type=None)`: Build an `AggregateCursor` (not a coroutine)

---

### 3. Cursor - Query Results with Chaining

**Purpose**: Build and execute MongoDB queries with a fluent interface.

**Description**: `Cursor` represents query results and supports chaining methods for complex queries. Results are automatically deserialized to Pydantic models.

#### Example

```python
from aasu import Database, APIModel

class Order(APIModel):
    id: str
    customer_id: str
    total: float
    status: str

orders_col = db.collection("orders", Order, primary_key="id")

async def main():
    # Basic find
    cursor = orders_col.find({"status": "pending"})

    # Chain operations (the chained methods are sync; only .all()/.first() are awaited)
    results = await (orders_col
        .find({"customer_id": "CUST123"})
        .filter({"status": "completed"})
        .skip(10)
        .limit(5)
        .project({"id": 1, "total": 1})
        .all()
    )

    # Get just first result
    first_order = await cursor.first()

    # Iterate through results (async)
    async for order in cursor:
        print(f"Order {order.id}: ${order.total}")

    # Get all results
    all_orders = await cursor.all()
```

#### Cursor Methods

- `filter(filters)`: Add additional filter conditions (chainable, sync)
- `limit(limit)`: Limit number of results (chainable, sync)
- `skip(skip)`: Skip N documents (chainable, sync)
- `project(projection)`: Select specific fields (chainable, sync)
- `sort(*pairs, **kwargs)`: Sort by `(field, direction)` pairs (chainable, sync)
- `await first()`: Get first result or None
- `await all()`: Get all results as a list
- `__aiter__()`: Async-iterate through results (`async for ...`)

---

### 4. AggregateCursor - MongoDB Aggregation Pipeline

**Purpose**: Execute complex MongoDB aggregation pipelines.

**Description**: `AggregateCursor` enables building and executing aggregation pipelines for data transformation and analysis.

#### Example

```python
from aasu import Database, APIModel

class Sale(APIModel):
    id: str
    product_id: str
    quantity: int
    amount: float
    date: str

sales_col = db.collection("sales", Sale, primary_key="id")

# Create aggregation pipeline
pipeline = [
    {"$match": {"date": {"$gte": "2024-01-01"}}},
    {"$group": {
        "_id": "$product_id",
        "total_quantity": {"$sum": "$quantity"},
        "total_amount": {"$sum": "$amount"}
    }},
    {"$sort": {"total_amount": -1}}
]

async def main():
    # Execute aggregation
    cursor = sales_col.aggregate(pipeline)

    # Add more pipeline stages
    cursor.add_line(
        {"$limit": 10}
    )

    # Get results (async iteration)
    async for result in cursor:
        print(f"Product {result['_id']}: {result['total_quantity']} units, ${result['total_amount']}")

    # Or get all at once
    results = await sales_col.aggregate(pipeline).all()
```

#### AggregateCursor Methods

- `add_line(*pipeline)`: Add stages to the aggregation pipeline (chainable, sync)
- `await first()`: Get first result or None
- `await all()`: Get all results as a list
- `__aiter__()`: Async-iterate through aggregation results (`async for ...`)

---

### 5. CacheDatabase and CacheController - Redis Caching

**Purpose**: Manage application-wide caching with automatic expiration and type safety.

**Description**: `CacheDatabase` wraps Redis connections and manages `CacheController` instances. `CacheController` provides typed caching with automatic serialization of Pydantic models.

#### Example

```python
from aasu import CacheDatabase, APIModel
from redis import Redis
from datetime import datetime, timedelta

class UserCache(APIModel):
    id: int
    name: str
    email: str

# Initialize cache database
redis_client = Redis.from_url("redis://localhost:6379")
cache_db = CacheDatabase(redis_client)

# Create controllers for different cache namespaces
user_cache = cache_db.cacher("user", UserCache, default_expiration=3600)
session_cache = cache_db.cacher("session", model=None)  # For string values

# Set and get cached values
user = UserCache(id=1, name="Alice", email="alice@example.com")
user_cache.set("user:123", user)  # Expires in 3600 seconds (default)
user_cache["user:456"] = user  # Alternative dict-like syntax

# Retrieve cached value
cached_user = user_cache.get("user:123")
# Returns: UserCache(id=1, name='Alice', email='alice@example.com')

# Dict-like access
user = user_cache["user:456"]

# Set with custom expiration
user_cache.set("user:789", user, expires_in=7200)  # 2 hours
user_cache.set("user:temp", user, expires_at=datetime.now() + timedelta(minutes=5))

# Pop (get and delete)
popped = user_cache.pop("user:789")

# Get with expiration modification
cached = user_cache.getex("user:456", expires_in=1800)  # Reset to 30 mins

# Atomic get and set
old_user = user_cache.getset("user:999", user)

# Check TTL (time to live in seconds, -1 if no expiration, -2 if not exists)
ttl = user_cache.ttl("user:456")
```

#### CacheController Methods

- `set(key, value, expires_in=None, expires_at=None, keep_ttl=False)`: Store value with optional expiration
- `get(key)`: Retrieve cached value or None
- `pop(key)`: Get and delete value
- `getex(key, expires_in=None, expires_at=None, persist=False)`: Get and optionally update expiration
- `getset(key, value)`: Atomic get-then-set operation
- `ttl(key)`: Get time-to-live in seconds
- `__getitem__(key)` / `__setitem__(key, value)`: Dict-like access

---

### 6. JWT Authentication - Token-Based Auth

**Purpose**: Generate, verify, and load JWT tokens with custom claim validation.

**Description**: `JwtAuthConfig` defines authentication configuration, while `JwtAuthenticator` handles token generation and validation with optional custom verification.

#### Example

```python
from aasu import JwtAuthConfig, JwtAuthenticator, APIModel
from jwt import PyJWK
from datetime import datetime

# Define the authentication data structure
class UserAuthData(APIModel):
    user_id: int
    username: str
    role: str

# Create a custom authenticator with verification
class UserAuthenticator(JwtAuthenticator, model=UserAuthData):
    
    @staticmethod
    def verify_jwt(token: str) -> None:
        """Optional: Add custom token verification logic"""
        if len(token) < 20:
            raise ValueError("Token too short")
    
    @staticmethod
    def verify_data(data: dict) -> None:
        """Optional: Add custom data validation"""
        allowed_roles = ["admin", "user", "guest"]
        if data.get("role") not in allowed_roles:
            raise ValueError("Invalid role")

# Create JWT configuration
key = PyJWK.from_json("""
{
    "kty": "RSA",
    "use": "sig",
    "n": "...",
    "e": "AQAB",
    "kid": "key1"
}
""")  # Or use a simple string for HS256

config = JwtAuthConfig(
    key="your-secret-key",  # For HS256
    issuer="your-app",
    expires_in=3600  # 1 hour
)

# Generate a token
auth_data = UserAuthData(user_id=123, username="alice", role="admin")
token = UserAuthenticator.generate(
    auth_data,
    config,
    extra_data={"ip": "192.168.1.1"}
)
# Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...."

# Load and verify a token
try:
    authenticator = UserAuthenticator.load(token, config)
    print(f"User: {authenticator.data.username}")
    print(f"Role: {authenticator.data.role}")
except JwtDenied as e:
    print(f"Authentication failed: {e}")
```

#### JwtAuthConfig Properties

- `key`: PyJWK or secret string for signing/verifying
- `issuer`: Optional issuer claim
- `audience`: Optional list of allowed audiences
- `expires_in`: Optional token expiration in seconds

#### JwtAuthenticator Methods

- `generate(obj, config, extra_data=None)`: Generate a signed JWT token
- `load(token, config, opts=None)`: Load and verify a token
- `verify_jwt(token)`: Optional override for custom token validation
- `verify_data(data)`: Optional override for custom data validation

---

### 7. FastAPICompatibleJSONResponse - FastAPI Integration

**Purpose**: Custom JSON response serializer for FastAPI that handles APIModel instances.

**Description**: `FastAPICompatibleJSONResponse` extends FastAPI's JSONResponse to automatically serialize `APIModel` instances using the `apiserialize` method.

#### Example

```python
from fastapi import FastAPI
from aasu import APIModel, FastAPICompatibleJSONResponse, apiserialize

app = FastAPI()

class Product(APIModel):
    id: int
    name: str
    price: float

@app.get("/product/{product_id}", response_class=FastAPICompatibleJSONResponse)
async def get_product(product_id: int):
    product = Product(id=product_id, name="Laptop", price=999.99)
    return product  # Automatically serialized via apiserialize

@app.get("/products", response_class=FastAPICompatibleJSONResponse)
async def list_products():
    products = [
        Product(id=1, name="Laptop", price=999.99),
        Product(id=2, name="Mouse", price=29.99)
    ]
    return {"items": products}  # APIModel instances are automatically serialized
```

#### Key Features

- Automatically serializes `APIModel` instances in responses
- Maintains compatibility with standard JSON responses
- No need to manually call `apiserialize()` in route handlers
- Handles nested `APIModel` objects

---

## Integration Example - Complete Application

```python
from fastapi import FastAPI, HTTPException
from aasu import (
    Database, APIModel, CacheDatabase, 
    JwtAuthenticator, JwtAuthConfig, FastAPICompatibleJSONResponse
)
from redis import Redis
import jwt as pyjwt

app = FastAPI()

# Models
class User(APIModel):
    id: int
    username: str
    email: str

class AuthData(APIModel):
    user_id: int
    username: str

# Initialize services
db = Database("mongodb://localhost:27017", "app_db")
cache_db = CacheDatabase(Redis.from_url("redis://localhost"))

users_col = db.collection("users", User, primary_key="id")
user_cache = cache_db.cacher("user", User, default_expiration=3600)

# Auth setup
class UserAuthenticator(JwtAuthenticator, model=AuthData):
    pass

auth_config = JwtAuthConfig(key="secret-key", expires_in=86400)

# Routes
@app.get("/users/{user_id}", response_class=FastAPICompatibleJSONResponse)
async def get_user(user_id: int):
    # Check cache first
    cached = user_cache.get(str(user_id))
    if cached:
        return cached
    
    # Query database (async)
    user = await users_col.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cache result
    user_cache.set(str(user_id), user)
    return user

@app.post("/auth/login", response_class=FastAPICompatibleJSONResponse)
async def login(user_id: int, username: str):
    auth_data = AuthData(user_id=user_id, username=username)
    token = UserAuthenticator.generate(auth_data, auth_config)
    return {"token": token, "user_id": user_id}

@app.get("/protected", response_class=FastAPICompatibleJSONResponse)
async def protected_route(authorization: str):
    try:
        token = authorization.replace("Bearer ", "")
        authenticator = UserAuthenticator.load(token, auth_config)
        return {"message": f"Hello {authenticator.data.username}"}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## Error Handling

The library provides custom exceptions:

```python
from aasu.exceptions import AAsuError, JwtDenied

# JWT authentication errors
try:
    authenticator = UserAuthenticator.load(bad_token, config)
except JwtDenied as e:
    print(f"Token verification failed: {e}")

# Base error for other aasu errors
except AAsuError as e:
    print(f"Aasu error: {e}")
```

---

## Requirements

- Python >= 3.10
- pydantic >= 2.13.4
- fastapi >= 0.136.3
- motor >= 3.6.0
- redis >= 7.4.0
- pyjwt >= 2.13.0

---

## License

MIT

---

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
