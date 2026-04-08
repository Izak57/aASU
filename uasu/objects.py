from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder



class APIModel(BaseModel):

    def serialize(self, privacy: str | None = None):
        return self.model_dump(mode="json")
    


def apiserialize(obj: APIModel | BaseModel,
                 privacy: str | None = None):
    if isinstance(obj, APIModel):
        l1 = obj.serialize(privacy=privacy)
    else:
        l1 = obj.model_dump(mode="json")

    secure_layer = jsonable_encoder(l1)
    return secure_layer
