import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from access.app.services import SessionCache


class TestSessionCacheGet:
    def test_get_without_put_returns_none(self):
        """
        Given an empty cache,
        When get is called for any key,
        Then None is returned.
        """
        cache = SessionCache()
        assert cache.get("admin", 1) is None

    def test_put_then_get_returns_version(self):
        """
        Given a fresh cache,
        When a version is put and then retrieved for the same key,
        Then the cached version is returned.
        """
        cache = SessionCache()
        cache.put("admin", 1, 42)
        assert cache.get("admin", 1) == 42

    def test_put_twice_last_version_wins(self):
        """
        Given a cache with an existing entry,
        When put is called again for the same key with a different version,
        Then the latest version is returned.
        """
        cache = SessionCache()
        cache.put("admin", 1, 1)
        cache.put("admin", 1, 99)
        assert cache.get("admin", 1) == 99


class TestSessionCacheInvalidate:
    def test_put_invalidate_get_returns_none(self):
        """
        Given a cached entry,
        When invalidate is called for that key,
        Then get returns None.
        """
        cache = SessionCache()
        cache.put("customer", 7, 5)
        cache.invalidate("customer", 7)
        assert cache.get("customer", 7) is None

    def test_invalidate_missing_key_is_noop(self):
        """
        Given an empty cache,
        When invalidate is called,
        Then no exception is raised.
        """
        cache = SessionCache()
        cache.invalidate("admin", 999)


class TestSessionCacheExpiry:
    def test_expired_entry_returns_none(self):
        """
        Given a cache with TTL=0,
        When put is called and then get is called immediately,
        Then None is returned because the entry has already expired.
        """
        cache = SessionCache(_ttl_seconds=0)
        cache.put("admin", 1, 10)
        # TTL=0 means expires_at == put time; monotonic() is >= that by now
        assert cache.get("admin", 1) is None

    def test_expired_entry_is_removed_from_store(self):
        """
        Given a cache with TTL=0,
        When get is called after expiry,
        Then the stale entry is pruned from the internal store.
        """
        cache = SessionCache(_ttl_seconds=0)
        cache.put("admin", 1, 10)
        cache.get("admin", 1)
        # Direct store access via object.__getattribute__ since slots hide it
        assert len(cache._store) == 0


class TestSessionCacheIsolation:
    def test_different_account_types_are_independent(self):
        """
        Given entries for the same sub but different account_types,
        When one is invalidated,
        Then the other is unaffected.
        """
        cache = SessionCache()
        cache.put("admin", 1, 10)
        cache.put("customer", 1, 20)
        cache.invalidate("admin", 1)
        assert cache.get("admin", 1) is None
        assert cache.get("customer", 1) == 20

    def test_different_subs_are_independent(self):
        """
        Given entries for the same account_type but different subs,
        When one is retrieved,
        Then the other is unaffected.
        """
        cache = SessionCache()
        cache.put("admin", 1, 11)
        cache.put("admin", 2, 22)
        assert cache.get("admin", 1) == 11
        assert cache.get("admin", 2) == 22


class TestSessionCacheClear:
    def test_clear_empties_all_entries(self):
        """
        Given multiple entries across different keys,
        When clear is called,
        Then all subsequent gets return None.
        """
        cache = SessionCache()
        cache.put("admin", 1, 1)
        cache.put("customer", 2, 2)
        cache.put("admin", 3, 3)
        cache.clear()
        assert cache.get("admin", 1) is None
        assert cache.get("customer", 2) is None
        assert cache.get("admin", 3) is None


class TestSessionCacheThreadSafety:
    def test_concurrent_puts_no_race(self):
        """
        Given 100 concurrent put operations across distinct keys,
        When all futures complete,
        Then each key is retrievable with the value that was written.
        """
        cache = SessionCache()
        n = 100

        def put_entry(i: int) -> None:
            cache.put("customer", i, i * 10)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(put_entry, i) for i in range(n)]
            for f in as_completed(futures):
                f.result()  # propagate any exception

        for i in range(n):
            assert cache.get("customer", i) == i * 10
