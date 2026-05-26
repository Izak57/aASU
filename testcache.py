from datetime import date
from secrets import token_hex
from time import sleep

from pydantic import Field
import uasu
from redis import Redis


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
            "birthday": self.birth.isoformat()
        }


d = uasu.CacheDatabase(Redis.from_url("redis://127.0.0.1:6379"))

UserCache = d.cacher("users", User, default_expiration=1)

w = User(
    name="Will",
    email="nn",
    birth=date(200, 5, 5)
)

UserCache[w.id] = w

print(UserCache[w.id])
sleep(2.5)
print(UserCache[w.id])
