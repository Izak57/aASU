# aASU

`aASU` is a small utility package for building API backends with:

- Pydantic-based API serialization
- MongoDB data access helpers
- Redis cache helpers
- FastAPI-compatible JSON responses
- JWT auth token helpers

---

## Installation

```bash
pip install -r requirements.txt
```

Requirements:

- Python 3.10+
- MongoDB (for database features)
- Redis (for cache features)

---

## Public API

From `uasu`:

- `APIModel`
- `apiserialize`
- `Database`
- `Collection`
- `CacheDatabase`
- `FastAPICompatibleJSONResponse`

Additional feature module:

- `uasu.auth` (`JwtAuthConfig`, `JwtAuthenticator`)

---

## Feature 1: API Models and Safe Serialization

### What it does

- `APIModel` extends Pydantic `BaseModel`.
- Override `apiserialize()` to control what fields are exposed in API responses.
- `apiserialize(obj)` serializes both `APIModel` and regular `BaseModel`.

### Example

```python
from datetime import date
from secrets import token_hex
import uasu
from pydantic import Field

class User(uasu.APIModel):
    id: str = Field(default_factory=lambda: token_hex(4))
    name: str
    email: str
    birth: date
    token: str = Field(default_factory=lambda: token_hex(32))

    def apiserialize(self, privacy: str | None = None):
        return {
            "id": self.id,
            "name": self.name,
            "birthday": self.birth.isoformat(),
        }

user = User(name="Izak", email="izak@example.com", birth=date(2009, 8, 3))
print(uasu.apiserialize(user))
```

---

## Feature 2: MongoDB Database Wrapper

### What it does

- `Database` wraps `pymongo.MongoClient`.
- `collection(name, model=...)` returns a typed `Collection`.
- `Collection` supports:
  - `insert(...)`
  - `find(...)`
  - `find_one(...)`
  - `get(primary_key_value)`
  - `aggregate(pipeline)`

### Example

```python
import uasu
from pydantic import BaseModel

class User(BaseModel):
    id: str
    name: str

db = uasu.Database("mongodb://localhost:27017", "uasu_test")
users = db.collection("users", User, primary_key="id")

users.insert(User(id="u1", name="Izak"))
print(users.get("u1"))
print(users.find({"name": "Izak"}).limit(10).all())
```

---

## Feature 3: Query Cursor Helpers

### What it does

`Collection.find()` returns a `Cursor` with chainable operations:

- `.filter({...})`
- `.limit(n)`
- `.skip(n)`
- `.project({...})`
- `.first()`
- `.all()`

`Collection.aggregate()` returns `AggregateCursor` and supports:

- Iteration over pipeline results
- `.add_line({...}, {...})` to append pipeline stages

### Example

```python
cursor = users.find({"active": True}).project({"name": 1, "_id": 0}).limit(5)
for row in cursor:
    print(row)

agg = users.aggregate([
    {"$group": {"_id": "$name", "count": {"$sum": 1}}}
]).add_line({"$sort": {"count": -1}})

for row in agg:
    print(row)
```

---

## Feature 4: Redis Cache Wrapper

### What it does

- `CacheDatabase` manages Redis-backed cache controllers.
- `cacher(prefix, model=..., default_expiration=...)` creates a `CacheController`.
- `CacheController` supports:
  - dictionary-style `controller[key] = value` and `controller[key]`
  - `set`, `get`, `pop`
  - `getex`, `getset`
  - `ttl`

Values can be plain strings or Pydantic models.

### Example

```python
from datetime import date
from redis import Redis
from pydantic import BaseModel
import uasu

class User(BaseModel):
    id: str
    name: str
    birth: date

cdb = uasu.CacheDatabase(Redis.from_url("redis://127.0.0.1:6379"))
user_cache = cdb.cacher("users", User, default_expiration=60)

user_cache.set("u1", User(id="u1", name="Izak", birth=date(2009, 8, 3)))
print(user_cache.get("u1"))
print(user_cache.ttl("u1"))
print(user_cache.pop("u1"))
```

---

## Feature 5: FastAPI-Compatible JSON Response

### What it does

`FastAPICompatibleJSONResponse` ensures FastAPI can encode `APIModel` instances using their `apiserialize()` output.

### Example

```python
from fastapi import FastAPI
import uasu

app = FastAPI(default_response_class=uasu.FastAPICompatibleJSONResponse)

@app.get("/health")
def health():
    return {"ok": True}
```

---

## Feature 6: JWT Authentication Helpers

### What it does

In `uasu.auth`:

- `JwtAuthConfig` stores JWT settings.
- `JwtAuthenticator.generate(...)` creates a JWT payload from a Pydantic model.
- `JwtAuthenticator.load(...)` decodes token data back into your auth data model.

### Example

```python
from pydantic import BaseModel
from uasu.auth import JwtAuthConfig, JwtAuthenticator
from jwt import PyJWK

class AuthData(BaseModel):
    user_id: str
    role: str

class AppAuth(JwtAuthenticator[AuthData], model=AuthData):
    pass

jwk = PyJWK.from_json('{"kty":"oct","k":"c2VjcmV0","alg":"HS256"}')
config = JwtAuthConfig(key=jwk, issuer="my-app")

token = AppAuth.generate(AuthData(user_id="u1", role="admin"), config)
auth = AppAuth.load(token, config)
print(auth.data)
```

---

## End-to-End FastAPI Example

```python
from fastapi import FastAPI, HTTPException
import uasu

app = FastAPI(default_response_class=uasu.FastAPICompatibleJSONResponse)
db = uasu.Database("mongodb://localhost:27017", "uasu_test")
users = db.collection("users")

@app.get("/users/{id}")
def get_user(id: str):
    user = users.get(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

Run:

```bash
uvicorn --host 0.0.0.0 --port 8080 --reload api:app
```

---

## Notes

- Redis and MongoDB must be reachable from your runtime.
- `JwtAuthenticator` currently decodes tokens with optional PyJWT options and issuer checks.
- `APIModel.apiserialize()` is the recommended place to hide private fields from API output.
