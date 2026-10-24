import re
import unittest
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from main import BLOCKED_MAX_PAUSE_SECONDS, BLOCKED_PAUSE_SECONDS, ScrapeRetry, main, parse_shard
from otodom_scraper import OtodomBlockedError


class ScrapeRetryTest(unittest.TestCase):
    def setUp(self):
        sleep_patcher = patch("main.sleep")
        self.sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        self.scraper = MagicMock()

    @staticmethod
    def _failing(errors, result="ok"):
        remaining = list(errors)

        def call():
            if remaining:
                raise remaining.pop(0)
            return result

        call.__name__ = "call"
        return call

    def test_returns_result_after_transient_failures(self):
        retry = ScrapeRetry(self.scraper, max_tries=3)
        self.assertEqual("ok", retry(self._failing([ValueError(), ValueError()])))

    def test_raises_after_max_tries(self):
        retry = ScrapeRetry(self.scraper, max_tries=2)
        with self.assertRaises(ValueError):
            retry(self._failing([ValueError(), ValueError(), ValueError()]))

    def test_blocks_do_not_use_up_ordinary_tries(self):
        retry = ScrapeRetry(self.scraper, max_tries=1, max_blocked_tries=5)
        blocked = [OtodomBlockedError() for _ in range(4)]
        self.assertEqual("ok", retry(self._failing(blocked)))
        self.assertEqual(4, self.scraper.reset_session.call_count)

    def test_block_pause_doubles_and_caps(self):
        retry = ScrapeRetry(self.scraper, max_blocked_tries=20)
        retry(self._failing([OtodomBlockedError() for _ in range(10)]))
        pauses = [c.args[0] for c in self.sleep.call_args_list]
        self.assertEqual(BLOCKED_PAUSE_SECONDS, pauses[0])
        self.assertEqual(BLOCKED_PAUSE_SECONDS * 2, pauses[1])
        self.assertEqual(BLOCKED_MAX_PAUSE_SECONDS, pauses[-1])

    def test_backoff_carries_over_between_items_until_a_success(self):
        retry = ScrapeRetry(self.scraper, max_blocked_tries=2)
        with self.assertRaises(OtodomBlockedError):
            retry(self._failing([OtodomBlockedError(), OtodomBlockedError()]))
        with self.assertRaises(OtodomBlockedError):
            retry(self._failing([OtodomBlockedError(), OtodomBlockedError()]))
        self.assertEqual(BLOCKED_PAUSE_SECONDS * 8, self.sleep.call_args_list[-1].args[0])

        retry(self._failing([]))
        self.assertEqual(0, retry.consecutive_blocks)



class ShardTest(unittest.TestCase):
    def test_a_shard_is_parsed_into_index_and_count(self):
        self.assertEqual((2, 3), parse_shard("2/3"))

    def test_no_shard_means_everything(self):
        self.assertIsNone(parse_shard(None))

    def test_malformed_shards_are_rejected(self):
        for value in ("2", "0/2", "3/2", "a/b", "1/0", "-1/2"):
            with self.assertRaises(typer.BadParameter, msg=value):
                parse_shard(value)


class OnlyMissingLocationsFlagTest(unittest.TestCase):
    def test_the_flag_needs_the_update_pass(self):
        app = typer.Typer()
        app.command()(main)

        result = CliRunner().invoke(app, ["--no-update", "--only-missing-locations"])

        self.assertNotEqual(0, result.exit_code)
        self.assertIn("--only-missing-locations requires --update", re.sub(r"\x1b\[[0-9;]*m", "", result.output))



class RadiusFlagTest(unittest.TestCase):
    def __invoke(self, *arguments):
        app = typer.Typer()
        app.command()(main)
        result = CliRunner().invoke(app, list(arguments))
        return result.exit_code, re.sub(r"\x1b\[[0-9;]*m", "", result.output)

    def test_the_radius_needs_a_city(self):
        exit_code, output = self.__invoke("--radius-km", "15")

        self.assertNotEqual(0, exit_code)
        self.assertIn("--radius-km requires --city", output)

    def test_only_radii_otodom_offers_are_accepted(self):
        exit_code, output = self.__invoke("--voivodeship", "malopolskie", "--city", "krakow", "--radius-km", "12")

        self.assertNotEqual(0, exit_code)
        self.assertIn("--radius-km must be one of", output)


if __name__ == "__main__":
    unittest.main()
