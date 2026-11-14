import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.config import list_brands  # noqa: E402
from studio.project import Project  # noqa: E402


@pytest.fixture(params=list_brands())
def project(request, tmp_path):
    """A freshly curated project for every brand, in an isolated workspace."""
    return Project.open(request.param, workspace=tmp_path, fresh=True)


@pytest.fixture
def jpeg_bytes():
    def make(size=(1200, 1500), color=(200, 80, 60)):
        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, "JPEG")
        return buf.getvalue()
    return make
