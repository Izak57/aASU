from typing import Annotated
from datetime import date
from secrets import token_hex

from fastapi import FastAPI, Body, HTTPException
from pydantic import Field
import uasu



class User(uasu.APIModel):
    id: str = Field(default_factory=lambda: token_hex(4))
    name: str
    email: str
    birth: date
    token: str = Field(default_factory=lambda: token_hex(32))

    def serialize(self, privacy: str | None = None):
        return {
            "id": self.id,
            "name": self.name,
            "birthday": self.birth.isoformat()
        }



app = FastAPI()

users: list[User] = [
    User(id="izak",name="Izak",
         email="izak@tuffapi.com", birth=date(2009, 8, 3))
]



@app.get("/hello")
def hello():
    return {"Hello": "World"}


@app.post("/user/{id}/new")
def create_user(id: str,
                name: Annotated[str, Body()],
                email: Annotated[str, Body()],
                birth: Annotated[date, Body()]):
    user = User(id=id, name=name, email=email, birth=birth)
    users.append(user)
    return uasu.apiserialize(user)


@app.get("/user/{id}")
def get_user(id: str):
    user = next((u for u in users if u.id == id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return uasu.apiserialize(user)
