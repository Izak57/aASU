from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder


__all__ = ["APIModel", "apiserialize"]



class APIModel(BaseModel):
    """Base Pydantic model with API serialization support."""

    def apiserialize(self, privacy: str | None = None):
        """Serialize the model to a JSON-compatible dict, optionally filtered by privacy level."""
        return self.model_dump(mode="json")
    


def apiserialize(obj: APIModel | BaseModel,
                 privacy: str | None = None):
    """Serialize an APIModel or BaseModel to a JSON-compatible dict.

    If the object is an APIModel, its custom apiserialize method is used.
    The result is then passed through FastAPI's jsonable_encoder.
    """
    if isinstance(obj, APIModel):
        l1 = obj.apiserialize(privacy=privacy)
    else:
        l1 = obj.model_dump(mode="json")

    secure_layer = jsonable_encoder(l1)
    return secure_layer
