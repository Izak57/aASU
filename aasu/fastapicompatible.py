from typing import Any
from json import dumps

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.datastructures import DefaultPlaceholder

from .objects import APIModel, apiserialize


__all__ = ["FastAPICompatibleJSONResponse", "useapp"]



class FastAPICompatibleJSONResponse(JSONResponse):

    def render(self, content: Any) -> bytes:
        print("rendering ahh", content, apiserialize(content))
        return super().render(apiserialize(content))


def compatible_renderer(self, content: Any) -> bytes:
    content = apiserialize(content)
    return super(self).render(content)


def useapp(app: FastAPI) -> FastAPI:
    respclass = app.router.default_response_class
    if isinstance(respclass, DefaultPlaceholder):
        app.router.default_response_class = FastAPICompatibleJSONResponse

    elif issubclass(respclass, JSONResponse):
        app.router.default_response_class.render = compatible_renderer
    return app
