from aasu import APIModel, apiserialize
from rich import print



class User(APIModel):
    id: int
    name: str
    token: str


    def apiserialize(self, privacy: str | None = None):
        return {"userId": self.id, "username": self.name}


resp = {
    "user": [User(id=1, name="Alice", token="secret-token")]
}


print(apiserialize(resp))
