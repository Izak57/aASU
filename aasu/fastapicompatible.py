from typing import Any
from json import dumps

from fastapi import FastAPI
from fastapi import encoders
from fastapi.responses import JSONResponse
from fastapi.datastructures import DefaultPlaceholder

from .objects import APIModel, apiserialize


__all__ = ["FastAPICompatibleJSONResponse", "useapp"]



class FastAPICompatibleJSONResponse(JSONResponse):

    def render(self, content: Any) -> bytes:
        return super().render(apiserialize(content))


def compatible_renderer(self, content: Any) -> bytes:
    content = apiserialize(content)
    return super(self).render(content)


def patch_encoder():
    old = encoders.jsonable_encoder

    def new(obj, **kwargs):
        if isinstance(obj, APIModel):
            return apiserialize(obj)
        return old(obj, **kwargs)

    encoders.jsonable_encoder = new


def useapp(app: FastAPI) -> FastAPI:
    respclass = app.router.default_response_class
    if isinstance(respclass, DefaultPlaceholder):
        app.router.default_response_class = FastAPICompatibleJSONResponse

    elif issubclass(respclass, JSONResponse):
        app.router.default_response_class.render = compatible_renderer

    patch_encoder()
    return app
