from studio import curate, imaging
from studio.config import list_brands, load_brand


def test_grid_is_deterministic():
    lib = imaging.load_library()
    brand = load_brand(list_brands()[0])
    a, _ = curate.plan_grid(lib, brand)
    b, _ = curate.plan_grid(lib, brand)
    assert a.order == b.order and a.arch_bg == b.arch_bg


def test_grid_has_nine_unique_images_and_variety(project):
    ids = [p.image_id for p in project.posts]
    assert len(ids) == 9 and len(set(ids)) == 9
    assert len({project.library[i].category for i in ids}) >= 4


def test_arrangement_beats_the_median_layout(project):
    report = project.report
    assert report["layouts_searched"] == 362880
    assert report["energy_best"] < report["energy_median"] < report["energy_worst"]


def test_no_adjacent_photos_share_a_subject(project):
    cats = [project.library[p.image_id].category for p in project.posts]
    pairs = [(a, b) for a, b in curate.EDGES]
    same = sum(cats[a] == cats[b] for a, b in pairs)
    assert same <= 1


def test_checkerboard_templates(project):
    for cell, post in enumerate(project.posts):
        assert post.template == ("arch" if cell in curate.ARCH_CELLS else "full")


def test_stories_use_distinct_images_not_in_grid_when_possible(project):
    story_ids = [s.image_id for s in project.stories]
    assert len(set(story_ids)) == 3
    assert not set(story_ids) & {p.image_id for p in project.posts}


def test_brands_curate_differently():
    lib = imaging.load_library()
    plans = {b: curate.plan_grid(lib, load_brand(b))[0].order for b in list_brands()}
    assert len({tuple(v) for v in plans.values()}) == len(plans)
