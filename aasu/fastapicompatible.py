from typing import Any

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from .objects import APIModel, apiserialize


__all__ = ["FastAPICompatibleJSONResponse"]



class FastAPICompatibleJSONResponse(JSONResponse):

    def render(self, content: Any) -> bytes:
        encoded = jsonable_encoder(
            content,
            custom_encoder={
                APIModel: lambda o: apiserialize(o, privacy=None)
            }
        )
        return super().render(encoded)
