from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder


__all__ = ["APIModel", "apiserialize"]



class APIModel(BaseModel):

    def apiserialize(self, privacy: str | None = None):
        return self.model_dump(mode="json")
    


def apiserialize(obj: APIModel | BaseModel,
                 privacy: str | None = None):
    """Serializes the given object to a JSON-serializable format, using the
    apiserialize or model_dump method"""
    if isinstance(obj, APIModel):
        l1 = obj.apiserialize(privacy=privacy)
    else:
        l1 = obj.model_dump(mode="json")

    secure_layer = jsonable_encoder(l1)
    return secure_layer
