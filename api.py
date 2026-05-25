from typing import Annotated
from datetime import date
from secrets import token_hex

from fastapi import FastAPI, Body, HTTPException
from pydantic import Field
import uasu
from rich import print



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



app = FastAPI()
db = uasu.Database("mongodb://localhost:27017", "uasu_test")

UserTable = db.collection("users", User)






@app.get("/hello")
def hello():
    return {"Hello": "World"}


@app.get("/users")
def get_users():
    users = UserTable.find().all()
    return users
    return [uasu.apiserialize(u) for u in users]


@app.post("/users/{id}/new")
def create_user(id: str,
                name: Annotated[str, Body()],
                email: Annotated[str, Body()],
                birth: Annotated[date, Body()]):
    user = User(id=id, name=name, email=email, birth=birth)
    UserTable.insert(user)
    return uasu.apiserialize(user)


@app.get("/users/{id}")
def get_user(id: str):
    user = UserTable.get(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return uasu.apiserialize(user)
