"""Guard: the Signal Feed must never spend X API credits by default.
X credits are reserved for posting. Paid reads need two explicit env flags."""
import importlib, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

def load(env):
    for k in ("SIGNAL_FEED_PROVIDER", "SIGNAL_ALLOW_PAID_X_READS"):
        os.environ.pop(k, None)
    os.environ.update(env)
    import fetch_feed
    return importlib.reload(fetch_feed)

def test_default_is_free():
    assert load({}).USE_PAID_X_API is False

def test_provider_flag_alone_is_not_enough():
    assert load({"SIGNAL_FEED_PROVIDER": "x_api"}).USE_PAID_X_API is False

def test_paid_requires_both_flags():
    assert load({"SIGNAL_FEED_PROVIDER": "x_api", "SIGNAL_ALLOW_PAID_X_READS": "1"}).USE_PAID_X_API is True

def test_free_mapping_drops_reposts_and_replies():
    m = load({})
    rows = [{"type": "status", "id": "1", "text": "original post", "author": {"screen_name": "a"}, "created_timestamp": "1794533292", "likes": "5", "reposts": "1"},
            {"type": "status", "id": "2", "text": "repost", "author": {"screen_name": "a"}, "created_timestamp": "1794533292", "likes": "5", "reposts": "1", "reposted_by": {"x": 1}},
            {"type": "status", "id": "3", "text": "reply", "author": {"screen_name": "a"}, "created_timestamp": "1794533292", "likes": "5", "reposts": "1", "replying_to": "b"}]
    assert [r["id"] for r in m.fx_rows_to_xurl_shape(rows, "a")["data"]] == ["1"]

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"): fn(); print("ok", name)
