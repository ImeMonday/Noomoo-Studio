import io

import pytest

from studio.app import create_app


@pytest.fixture
def client(tmp_path):
    return create_app(workspace=tmp_path, dist=tmp_path / "dist").test_client()


def test_state_and_svg_endpoints(client):
    state = client.get("/api/hotel_marelle/state").json
    assert len(state["posts"]) == 9 and len(state["stories"]) == 3
    res = client.get("/api/hotel_marelle/svg/post/0")
    assert res.mimetype == "image/svg+xml" and b"<svg" in res.data


def test_replace_via_upload_and_errors(client, jpeg_bytes):
    ok = client.post("/api/tidehouse/replace", data={"kind": "story", "index": "1",
                                                     "file": (io.BytesIO(jpeg_bytes()), "photo.jpg")})
    assert ok.status_code == 200 and ok.json["stories"][1]["image_id"].startswith("upload-")
    bad = client.post("/api/tidehouse/replace", data={"kind": "post", "index": "99", "image_id": "x"})
    assert bad.status_code == 400
    junk = client.post("/api/tidehouse/replace", data={"kind": "post", "index": "0", "file": (io.BytesIO(b"nope"), "a.jpg")})
    assert junk.status_code == 400 and "readable" in junk.json["error"]


def test_unknown_brand_and_path_traversal(client):
    assert client.get("/api/nope/state").status_code == 404
    assert client.get("/fonts/../brands/tidehouse/brand.json").status_code == 404
    assert client.get("/download/tidehouse").status_code == 404   # nothing exported yet
