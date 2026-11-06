import random

from backend.agentdeal.assist import numbers_ok
from backend.agentdeal.assist_prompts import derive_mandate
from training.gen_assist_data import narrator_sample, parser_sample


def test_narrator_templates_keep_numbers():
    rng = random.Random(1)
    for _ in range(500):
        _, text, price, days = narrator_sample(rng)
        assert numbers_ok(text, price, days), text


def test_parser_labels_are_consistent():
    rng = random.Random(2)
    for _ in range(300):
        _, label = parser_sample(rng)
        if label["budget"] is not None:
            assert label["budget"] > 0
            if label["ideal_price"] is not None:
                assert label["ideal_price"] < label["budget"]
        if label["ideal_days"] is not None:
            assert label["ideal_days"] < label["latest_days"]


def test_derive_priorities():
    f, missing = derive_mandate({"budget": 4000, "latest_days": 10, "priority": "price"})
    assert (f["ideal_price"], f["ideal_days"], missing) == (2800, 9, [])
    f, _ = derive_mandate({"budget": 4000, "latest_days": 10, "priority": "speed"})
    assert (f["ideal_price"], f["ideal_days"]) == (3600, 4)
    f, _ = derive_mandate({"budget": 4000, "latest_days": 10, "priority": None})
    assert (f["ideal_price"], f["ideal_days"]) == (3400, 7)


def test_derive_keeps_explicit_and_reports_missing():
    f, missing = derive_mandate({"budget": 4000, "ideal_price": 3000, "latest_days": None})
    assert f["ideal_price"] == 3000 and missing == ["latest_days"]