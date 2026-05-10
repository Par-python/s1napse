"""Unit tests for the GitHub Releases updater pure helpers."""

import pytest

from s1napse.updater import _normalize_tag, _is_newer


class TestNormalizeTag:
    def test_strips_leading_v(self):
        assert _normalize_tag("v0.5.1-beta") == "0.5.1-beta"

    def test_no_prefix_unchanged(self):
        assert _normalize_tag("0.6.0-beta") == "0.6.0-beta"

    def test_uppercase_v_stripped(self):
        assert _normalize_tag("V1.0.0") == "1.0.0"

    def test_empty_returns_empty(self):
        assert _normalize_tag("") == ""


class TestIsNewer:
    def test_higher_patch_is_newer(self):
        assert _is_newer(remote="0.5.2-beta", local="0.5.1-beta") is True

    def test_higher_minor_is_newer(self):
        assert _is_newer(remote="0.6.0-beta", local="0.5.9-beta") is True

    def test_double_digit_patch_is_newer(self):
        # Naive string compare would say "0.5.10-beta" < "0.5.9-beta"; PEP 440 must not.
        assert _is_newer(remote="0.5.10-beta", local="0.5.9-beta") is True

    def test_same_version_is_not_newer(self):
        assert _is_newer(remote="0.5.1-beta", local="0.5.1-beta") is False

    def test_older_is_not_newer(self):
        assert _is_newer(remote="0.5.0-beta", local="0.5.1-beta") is False

    def test_stable_newer_than_beta(self):
        # 1.0.0 final is newer than 1.0.0-beta under PEP 440.
        assert _is_newer(remote="1.0.0", local="1.0.0-beta") is True

    def test_handles_v_prefix_on_either_side(self):
        assert _is_newer(remote="v0.6.0-beta", local="v0.5.1-beta") is True

    def test_invalid_remote_returns_false(self):
        # Garbage in -> never claim there's an update.
        assert _is_newer(remote="not-a-version", local="0.5.1-beta") is False

    def test_invalid_local_returns_false(self):
        assert _is_newer(remote="0.6.0", local="not-a-version") is False
