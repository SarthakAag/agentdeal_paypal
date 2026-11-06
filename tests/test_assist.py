from backend.agentdeal.assist import numbers_ok


def test_accepts_same_numbers():
    assert numbers_ok("I can do ₹3,518 with delivery in 8 days.", 3518.35, 8)


def test_rejects_changed_price():
    assert not numbers_ok("I can do ₹3,000 with delivery in 8 days.", 3518.35, 8)


def test_rejects_changed_days():
    assert not numbers_ok("I can do ₹3,518 with delivery in 5 days.", 3518.35, 8)


def test_rejects_extra_numbers():
    assert not numbers_ok("That is 10% off: ₹3,518 in 8 days.", 3518.35, 8)


def test_requires_both_numbers():
    assert not numbers_ok("I can do ₹3,518.", 3518.35, 8)