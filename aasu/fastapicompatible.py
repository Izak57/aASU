from typing import Any
from json import dumps

from fastapi import FastAPI
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
    import fastapi.encoders as _encoders
    import fastapi.routing as _routing
    import fastapi.dependencies.utils as _dep_utils

    old = _encoders.jsonable_encoder

    def new(obj, **kwargs):
        if isinstance(obj, APIModel):
            return apiserialize(obj)
        return old(obj, **kwargs)

    # Also patch all modules that captured a direct reference at import time
    _encoders.jsonable_encoder = new
    _routing.jsonable_encoder = new # type: ignore

    try:
        _dep_utils.jsonable_encoder = new
    except AttributeError:
        pass


def useapp(app: FastAPI) -> FastAPI:
    respclass = app.router.default_response_class
    if isinstance(respclass, DefaultPlaceholder):
        app.router.default_response_class = FastAPICompatibleJSONResponse

    elif issubclass(respclass, JSONResponse):
        app.router.default_response_class.render = compatible_renderer

    patch_encoder()
    return app
