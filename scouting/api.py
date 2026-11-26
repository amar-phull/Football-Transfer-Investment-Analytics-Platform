from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .engine import FEATURES, ROLES, rank, player_names

app = FastAPI(title="Recruitment desk",version="1.0")


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid",allow_inf_nan=False)
    role: Literal["FW","MF","DF","GK"] = "FW"
    season: str = "2025-2026"
    rate_bands: dict[str,int] | None = None
    weights: dict[str,float] | None = None
    minutes: int = Field(default=450,ge=1)
    max_minutes: int | None = Field(default=None,ge=1)
    min_budget: int | None = Field(default=None,ge=0)
    min_age: int | None = Field(default=None,ge=0,le=100)
    max_age: int | None = Field(default=None,ge=0,le=100)
    budget: int | None = Field(default=None,ge=0)
    currency: Literal["EUR","GBP","USD"] = "EUR"
    as_of: date | None = None
    player_name: str = ""
    search: str = ""
    league: str = ""
    offset: int = Field(default=0,ge=0)
    limit: int = Field(default=40,ge=1,le=200)


@app.get("/api/v1/names")
def names():
    return player_names()


@app.get("/api/v1/roles")
def roles():
    return {"profiles":ROLES,"labels":{k:v[0] for k,v in FEATURES.items()}}


@app.post("/api/v1/rankings")
def rankings(query: Query):
    try:
        return rank(**query.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


if Path("dist").is_dir():
    app.mount("/",StaticFiles(directory="dist",html=True),name="desk")
