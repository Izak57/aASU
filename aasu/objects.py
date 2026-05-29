from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder


__all__ = ["APIModel", "apiserialize"]



class APIModel(BaseModel):

    def apiserialize(self, privacy: str | None = None):
        return self.model_dump(mode="json")



def apiserialize(obj: APIModel | BaseModel | dict | list,
                 privacy: str | None = None):
    if isinstance(obj, APIModel):
        l1 = obj.apiserialize(privacy=privacy)

    elif isinstance(obj, BaseModel):
        l1 = obj.model_dump(mode="json")

    else:
        l1 = obj

    secure_layer = jsonable_encoder(l1, custom_encoder={
        APIModel: lambda o: apiserialize(o, privacy=privacy)
    })
    return secure_layer
