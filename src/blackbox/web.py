"""Local web page with the death journal."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from blackbox.journal import deaths
from blackbox.store import Store

TEMPLATES = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


def create_app(db: Path) -> FastAPI:
    app = FastAPI(title="blackbox")

    @app.get("/", response_class=HTMLResponse)
    def index():
        records = list(reversed(deaths(Store(db).events())))
        return TEMPLATES.get_template("index.html").render(deaths=records)

    return app
