from explainer.web.auth import hash_password, verify_password, SessionCodec


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


def test_session_issue_read_round_trip():
    codec = SessionCodec("secret-key")
    cookie = codec.issue(now=1000.0)
    assert codec.read(cookie, now=1000.0) is True


def test_session_rejects_tampered_cookie():
    codec = SessionCodec("secret-key")
    cookie = codec.issue(now=1000.0)
    ts, sig = cookie.rsplit(".", 1)
    forged = f"{int(ts) + 1}.{sig}"
    assert codec.read(forged, now=1000.0) is False


def test_session_rejects_wrong_key():
    cookie = SessionCodec("key-a").issue(now=1000.0)
    assert SessionCodec("key-b").read(cookie, now=1000.0) is False


def test_session_rejects_expired_cookie():
    codec = SessionCodec("secret-key", max_age_days=1)
    cookie = codec.issue(now=1000.0)
    later = 1000.0 + 2 * 86400  # 2 days later
    assert codec.read(cookie, now=later) is False


def test_session_rejects_garbage():
    codec = SessionCodec("secret-key")
    assert codec.read("", now=1000.0) is False
    assert codec.read("no-dot", now=1000.0) is False
    assert codec.read("notanint.deadbeef", now=1000.0) is False
