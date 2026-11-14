import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from studio import export
from studio.ai import AIClient, clean_caption, fallback_caption
from studio.config import ConfigError, load_brand
from studio.project import Project


# -- replacing images ----------------------------------------------------------------------------
def snapshot(project):
    return [(p.image_id, p.caption) for p in project.posts], [(s.image_id, s.fields) for s in project.stories]


def test_replace_post_changes_only_that_slot_and_locks_it(project, jpeg_bytes):
    before = snapshot(project)
    iid = project.add_upload(jpeg_bytes(), "my photo.jpg")
    project.replace("post", 3, iid)
    after = snapshot(project)
    assert after[0][3][0] == iid and project.posts[3].locked
    assert [p for i, p in enumerate(after[0]) if i != 3] == [p for i, p in enumerate(before[0]) if i != 3]
    assert after[1] == before[1]
    assert iid in project.post_svg(3) or "base64" in project.post_svg(3)


def test_replace_with_grid_image_swaps_slots(project):
    a, b = project.posts[0].image_id, project.posts[5].image_id
    project.replace("post", 0, b)
    assert project.posts[0].image_id == b and project.posts[5].image_id == a


def test_recurate_keeps_locked_slots(project, jpeg_bytes):
    iid = project.add_upload(jpeg_bytes(), "keep.jpg")
    project.replace("post", 4, iid)
    project.replace("story", 1, iid)
    project.curate(keep_locked=True)
    assert project.posts[4].image_id == iid and project.stories[1].image_id == iid
    assert len({p.image_id for p in project.posts}) == 9


def test_state_survives_reload(project, jpeg_bytes, tmp_path):
    iid = project.add_upload(jpeg_bytes(), "persist.jpg")
    project.replace("post", 2, iid)
    reopened = Project.open(project.brand_id, workspace=tmp_path)
    assert reopened.posts[2].image_id == iid


@pytest.mark.parametrize("data,msg", [(b"not an image", "readable"), (None, "too small")])
def test_upload_validation(project, jpeg_bytes, data, msg):
    payload = data if data is not None else jpeg_bytes(size=(300, 300))
    with pytest.raises(ValueError, match=msg):
        project.add_upload(payload, "x.jpg")


def test_edit_text_is_live_and_validated(project):
    project.set_field("story", 0, "headline", "A brand new headline")
    assert "A brand new headline".split()[0] in project.story_svg(0)
    with pytest.raises(ValueError):
        project.set_field("story", 0, "nonsense", "x")
    with pytest.raises(ValueError):
        project.set_field("post", 0, "caption", "x" * 500)


# -- export and repeatability ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("export")
    out = {}
    for run in ("a", "b"):
        ws = root / f"ws-{run}"
        project = Project.open("hotel_marelle", workspace=ws, fresh=True)
        out[run] = (export.export(project, root / f"dist-{run}"), root / f"dist-{run}" / "hotel_marelle")
    return out


def test_export_contains_all_deliverables(built):
    zip_path, folder = built["a"]
    assert len(list((folder / "png/posts").glob("*.png"))) == 9
    assert len(list((folder / "png/stories").glob("*.png"))) == 3
    assert len(list((folder / "source/svg").rglob("*.svg"))) == 12
    assert (folder / "preview.html").exists() and (folder / "CREDITS.md").exists()
    sizes = {p.name: Image.open(p).size for p in (folder / "png").rglob("*.png")}
    assert {sizes[f"post-0{i}.png"] for i in range(1, 10)} == {(1080, 1350)}
    assert {sizes[f"story-0{i}.png"] for i in range(1, 4)} == {(1080, 1920)}
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None
        assert any(n.endswith("story-01.svg") for n in zf.namelist())


def test_builds_are_byte_for_byte_repeatable(built):
    ma = json.loads((built["a"][1] / "manifest.json").read_text(encoding="utf-8"))
    mb = json.loads((built["b"][1] / "manifest.json").read_text(encoding="utf-8"))
    assert ma["sha256"] == mb["sha256"]
    assert built["a"][0].read_bytes() == built["b"][0].read_bytes()


# -- AI layer --------------------------------------------------------------------------------------
def test_ai_disabled_by_default_and_deterministic(project):
    assert not project.ai.enabled
    info = project.library[project.posts[0].image_id]
    assert project.caption_for(info.id) == fallback_caption(project.brand, project.content, info)


def test_ai_output_is_sanitised():
    brand = load_brand("hotel_marelle")
    assert clean_caption('"Golden hour, slowly."\nextra line', brand) == "Golden hour, slowly."
    assert clean_caption("A luxury escape", brand) is None
    assert clean_caption("Sunsets #blessed", brand) is None
    assert clean_caption("Sunsets \U0001F305", brand) is None
    assert clean_caption("x" * 100, brand) is None


def test_ai_end_to_end_against_local_stub_server(project, jpeg_bytes, tmp_path):
    import http.server
    import threading
    seen = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.update(auth=self.headers["Authorization"], path=self.path, model=body["model"])
            out = json.dumps({"choices": [{"message": {"content": "\"Slow light, warm stone.\""}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        project.ai = AIClient("openai_compat", f"http://127.0.0.1:{server.server_port}/v1", "qwen-plus", "secret",
                              cache_path=tmp_path / "ai.json")
        iid = project.add_upload(jpeg_bytes(), "terrace.jpg")
        assert project.caption_for(iid) == "Slow light, warm stone."
        assert seen == {"auth": "Bearer secret", "path": "/v1/chat/completions", "model": "qwen-plus"}
        curated = next(iter(project.content.captions))
        assert project.caption_for(curated) == project.content.captions[curated]   # model never overrides curated copy
        seen.clear()
        assert project.caption_for(iid) == "Slow light, warm stone." and not seen   # second call served from cache
    finally:
        server.shutdown()


def test_ai_failure_falls_back_without_raising(project):
    broken = AIClient("openai_compat", "http://127.0.0.1:9", "m", "key", cache_path=Path("/tmp/none-ai.json"), timeout=1)
    info = project.library[project.posts[0].image_id]
    assert broken.caption(project.brand, info, "fallback line") == "fallback line"


# -- config ----------------------------------------------------------------------------------------
def test_invalid_brand_is_rejected(tmp_path, monkeypatch):
    import studio.config as config
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "brand.json").write_text(json.dumps({
        "name": "x", "tagline": "x", "handle": "@x", "mark": "arch", "tile_backgrounds": ["primary"],
        "palette": {"ink": "red", "paper": "#FFFFFF", "primary": "#000000", "accent": "#000000", "soft": "#000000"},
        "fonts": {}, "voice": {}}), encoding="utf-8")
    monkeypatch.setattr(config, "BRANDS_DIR", tmp_path)
    with pytest.raises(ConfigError, match="palette.ink"):
        config.load_brand("bad")
