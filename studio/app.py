"""Flask web UI: live preview, image replacement, text editing, export."""
from __future__ import annotations

import io
import threading
from functools import wraps

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory
from PIL import Image

from . import export as exporter
from .ai import AIClient
from .config import DIST, FONTS_DIR, ROOT, list_brands
from .project import Project


def create_app(ai: AIClient | None = None, workspace=None, dist=DIST) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    ai = ai or AIClient.from_env()
    projects: dict = {}
    lock = threading.RLock()
    kw = {"workspace": workspace} if workspace else {}

    def project(brand_id: str) -> Project:
        if brand_id not in list_brands():
            abort(404, description="Unknown brand")
        if brand_id not in projects:
            projects[brand_id] = Project.open(brand_id, ai, **kw)
        return projects[brand_id]

    def locked(fn):
        @wraps(fn)
        def inner(*a, **k):
            with lock:
                return fn(*a, **k)
        return inner

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def http_error(exc):
        message = "Image is larger than 16 MB" if exc.code == 413 else (exc.description or "Bad request")
        return jsonify(error=message), exc.code

    @app.errorhandler(ValueError)
    @app.errorhandler(KeyError)
    @app.errorhandler(IndexError)
    def bad_input(exc):
        return jsonify(error=str(exc).strip("'\"") or "Invalid request"), 400

    @app.get("/")
    def index():
        return send_file(ROOT / "templates" / "studio.html")

    @app.get("/fonts/<path:name>")
    def fonts(name):
        return send_from_directory(FONTS_DIR, name)

    @app.get("/api/<brand_id>/state")
    @locked
    def state(brand_id):
        return jsonify(project(brand_id).to_dict())

    @app.get("/api/<brand_id>/svg/<kind>/<int:index>")
    @locked
    def svg(brand_id, kind, index):
        p = project(brand_id)
        if kind not in ("post", "story"):
            abort(404)
        body = p.post_svg(index, "/fonts/") if kind == "post" else p.story_svg(index, "/fonts/")
        return Response(body, mimetype="image/svg+xml")

    @app.get("/api/<brand_id>/thumb/<image_id>")
    @locked
    def thumb(brand_id, image_id):
        info = project(brand_id).library.get(image_id)
        if info is None:
            abort(404)
        with Image.open(info.path) as im:
            im = im.convert("RGB")
            im.thumbnail((320, 400))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
        return Response(buf.getvalue(), mimetype="image/jpeg", headers={"Cache-Control": "max-age=3600"})

    @app.post("/api/<brand_id>/replace")
    @locked
    def replace(brand_id):
        p = project(brand_id)
        kind, index = request.form.get("kind", ""), int(request.form.get("index", "-1"))
        if not 0 <= index < (9 if kind == "post" else 3):
            raise IndexError("Slot out of range")
        upload = request.files.get("file")
        image_id = p.add_upload(upload.read(), upload.filename or "") if upload else request.form.get("image_id", "")
        p.replace(kind, index, image_id)
        return jsonify(p.to_dict())

    @app.post("/api/<brand_id>/field")
    @locked
    def field(brand_id):
        body = request.get_json(force=True, silent=True) or {}
        p = project(brand_id)
        kind, index = body.get("kind"), int(body.get("index", -1))
        if kind not in ("post", "story") or not 0 <= index < (9 if kind == "post" else 3):
            raise IndexError("Slot out of range")
        value = body.get("value", "")
        if kind == "story" and isinstance(p.stories[index].fields.get(body.get("name")), list):
            value = str(value).split("\n")
        p.set_field(kind, index, body.get("name", ""), value)
        return jsonify(p.to_dict())

    @app.post("/api/<brand_id>/curate")
    @locked
    def curate(brand_id):
        body = request.get_json(force=True, silent=True) or {}
        p = project(brand_id)
        p.curate(keep_locked=bool(body.get("keep_locked", True)))
        return jsonify(p.to_dict())

    @app.post("/api/<brand_id>/reset")
    @locked
    def reset(brand_id):
        projects.pop(brand_id, None)
        projects[brand_id] = Project.open(brand_id, ai, fresh=True, **kw)
        return jsonify(projects[brand_id].to_dict())

    @app.post("/api/<brand_id>/export")
    @locked
    def do_export(brand_id):
        zip_path = exporter.export(project(brand_id), dist)
        return jsonify(zip=f"/download/{brand_id}", name=zip_path.name)

    @app.get("/download/<brand_id>")
    def download(brand_id):
        if brand_id not in list_brands():
            abort(404)
        path = dist / f"{brand_id}-assets.zip"
        if not path.exists():
            abort(404, description="Export first")
        return send_file(path, as_attachment=True)

    return app
