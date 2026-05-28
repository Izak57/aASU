from typing import Literal
from secrets import token_urlsafe

import aasu
from pydantic import Field, BaseModel
from fastapi import FastAPI, Depends, Body
from uvicorn import run


app = FastAPI()
db = aasu.Database("mongodb://localhost:27017/", "aasu_movies")

type Genre = Literal["horror", "drama", "animation", "romance", "action", "sci-fi"]
type Feature = Literal["no-ads", "admin", "upload"]

class Identifiable(aasu.APIModel):
    id: str = Field(default_factory=lambda: token_urlsafe(6))

class Movie(Identifiable):
    title: str
    vote: float
    genres: list[Genre]

    def apiserialize(self, privacy: str | None = None):
        return {
            "id": self.id,
            "title": self.title,
            "voteAverage": self.vote,
            "genres": ",".join(self.genres)
        }

class User(Identifiable):
    username: str
    features: list[Feature]

class UserAuthCtx(BaseModel):
    userid: str
    features: list[Feature]


movies = db.collection("movies", model=Movie)


def getMovie(id: str) -> Movie:
    mv = movies.get(id)
    if mv is None:
        raise
    return mv


@app.post("/movies/new")
def createMovie(title: str = Body(...),
                vote: float = Body(...),
                genres: list[Genre] = Body(...)):
    mv = Movie(title=title, vote=vote, genres=genres)
    movies.insert(mv)
    return aasu.apiserialize(mv)


@app.get("/movies")
def getAllMovies():
    mvs = movies.find({}).all()
    return [aasu.apiserialize(mv) for mv in mvs]


@app.get("/movies/{id}")
def getMovieDetail(mv: Movie = Depends(getMovie)):
    return aasu.apiserialize(mv)





run(app, host="127.0.0.1", port=6767)
