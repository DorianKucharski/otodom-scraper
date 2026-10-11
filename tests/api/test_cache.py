from __future__ import annotations

import unittest

from api.cache import RefreshingCache
from api.routers.facets import merge_feature_counts


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Loader:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def __call__(self) -> int:
        if self.fail:
            raise RuntimeError("database down")
        self.calls += 1
        return self.calls


def _cache(loader: _Loader, clock: _Clock, spawned: list) -> RefreshingCache[int]:
    return RefreshingCache(loader, max_age_seconds=60, clock=clock, spawn=spawned.append)


class TestRefreshingCache(unittest.TestCase):

    def test_the_first_read_loads_and_later_reads_reuse_it(self):
        loader, clock, spawned = _Loader(), _Clock(), []
        cache = _cache(loader, clock, spawned)

        self.assertEqual(1, cache.get())
        self.assertEqual(1, cache.get())
        self.assertEqual(1, loader.calls)

    def test_a_stale_value_is_served_while_a_refresh_runs_in_the_background(self):
        loader, clock, spawned = _Loader(), _Clock(), []
        cache = _cache(loader, clock, spawned)
        cache.get()
        clock.now = 61

        self.assertEqual(1, cache.get())
        self.assertEqual(1, len(spawned))

        spawned[0]()
        self.assertEqual(2, cache.get())

    def test_only_one_background_refresh_runs_at_a_time(self):
        loader, clock, spawned = _Loader(), _Clock(), []
        cache = _cache(loader, clock, spawned)
        cache.get()
        clock.now = 61

        cache.get()
        cache.get()

        self.assertEqual(1, len(spawned))

    def test_a_failed_background_refresh_keeps_the_old_value_and_allows_a_retry(self):
        loader, clock, spawned = _Loader(), _Clock(), []
        cache = _cache(loader, clock, spawned)
        cache.get()
        clock.now = 61
        loader.fail = True

        cache.get()
        spawned[0]()

        self.assertEqual(1, cache.get())
        self.assertEqual(2, len(spawned))


class TestFeatureCounts(unittest.TestCase):

    def test_synonyms_merge_into_one_facet_without_double_counting(self):
        facets = merge_feature_counts([("balkon", 112566), ("balcony", 93746), ("winda", 95161)])

        self.assertEqual([("balkon", 112566), ("winda", 95161)], [(facet.value, facet.count) for facet in facets])

    def test_facets_are_ranked_by_count_and_capitalised(self):
        facets = merge_feature_counts([("sauna", 3), ("LIFT", 10)])

        self.assertEqual(["Winda", "Sauna"], [facet.label for facet in facets])


if __name__ == "__main__":
    unittest.main()
