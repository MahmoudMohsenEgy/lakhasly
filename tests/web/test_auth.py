from explainer.web.auth import hash_password, verify_password


def test_hash_verify_round_trip():
    stored = hash_password("hunter2")
    assert "$" in stored
    assert verify_password("hunter2", stored) is True


def test_verify_rejects_wrong_password():
    stored = hash_password("hunter2")
    assert verify_password("wrong", stored) is False


def test_hash_is_salted_unique():
    assert hash_password("same") != hash_password("same")


def test_verify_rejects_malformed_stored():
    assert verify_password("x", "") is False
    assert verify_password("x", "no-dollar-sign") is False
    assert verify_password("x", "not_base64$also_not") is False
