"""Local web page with the death journal."""

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader

from blackbox.journal import character, deaths, level_chart, summary
from blackbox.store import Store

TEMPLATES = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


def create_app(db: Path) -> FastAPI:
    app = FastAPI(title="blackbox")

    @app.get("/", response_class=HTMLResponse)
    def index():
        store = Store(db)
        records = list(reversed(deaths(store.events(), store.pings(), store.snapshots(), store.clips())))
        return TEMPLATES.get_template("index.html").render(deaths=records, summary=summary(records))

    @app.get("/character/{name}", response_class=HTMLResponse)
    def character_page(name: str):
        store = Store(db)
        events = store.events()
        records = deaths(events, store.pings(), store.snapshots(), store.clips())
        c = character(events, records, name)
        if not c:
            raise HTTPException(404)
        chart = level_chart(c.levels, [d.ts for d in c.deaths])
        return TEMPLATES.get_template("character.html").render(c=c, chart=chart, deaths=list(reversed(c.deaths)))

    @app.get("/clip/{death_ts}")
    def clip(death_ts: str):
        from datetime import datetime

        path = Store(db).clips().get(datetime.fromisoformat(death_ts))
        if not path or not Path(path).exists():
            raise HTTPException(404)
        return FileResponse(path)

    return app
