"""Tests for Lovely-Sim-Racing/lovely-track-data integration in tools/import_tracks.py."""

import sys
from pathlib import Path

# tools/ isn't a package; import by adding its parent to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import import_tracks as it


class TestLovelyIdMap:
    def test_known_slugs_map_to_lovely_ids(self):
        assert it.LOVELY_ID_MAP['spa'] == 'spa'
        assert it.LOVELY_ID_MAP['monza'] == 'monza'
        assert it.LOVELY_ID_MAP['silverstone'] == 'silverstone'

    def test_hyphenated_lovely_ids_are_mapped(self):
        # Lovely uses hyphens; s1napse uses underscores in slugs.
        assert it.LOVELY_ID_MAP['brands_hatch'] == 'brands-hatch'
        assert it.LOVELY_ID_MAP['laguna_seca'] == 'laguna-seca'
        assert it.LOVELY_ID_MAP['mount_panorama'] == 'mount-panorama'
        assert it.LOVELY_ID_MAP['paul_ricard'] == 'paul-ricard'
        assert it.LOVELY_ID_MAP['red_bull_ring'] == 'red-bull-ring'
        assert it.LOVELY_ID_MAP['oulton_park'] == 'oulton-park'
        assert it.LOVELY_ID_MAP['watkins_glen'] == 'watkins-glen'

    def test_nordschleife_and_gp_are_distinct(self):
        # Lovely's data has typos; we map to the actual filenames they shipped.
        assert it.LOVELY_ID_MAP['nurburgring_24h'] == 'nurburgring-24h'
        assert it.LOVELY_ID_MAP['nurburgring'] == 'nurburgring'

    def test_every_value_corresponds_to_a_vendored_file(self):
        vendored = Path(__file__).resolve().parent.parent / 's1napse' / 'lovely-track-data'
        for s1_slug, lovely_id in it.LOVELY_ID_MAP.items():
            f = vendored / f'{lovely_id}.json'
            assert f.exists(), f'{s1_slug} -> {lovely_id}.json missing'


import math


class TestComputeTurnOffset:
    def _square_ccw(self):
        # Square traced counter-clockwise in normalized [0,1] frame, centered at (0.5, 0.5).
        # Corners: (0.2,0.2) -> (0.8,0.2) -> (0.8,0.8) -> (0.2,0.8) -> back.
        return [
            (0.2, 0.2), (0.5, 0.2), (0.8, 0.2),
            (0.8, 0.5), (0.8, 0.8), (0.5, 0.8),
            (0.2, 0.8), (0.2, 0.5),
        ]

    def test_offset_points_outward_for_ccw_polygon(self):
        # frac=0.125 -> index 1 = midpoint of bottom edge (0.5, 0.2) on the CCW square.
        # Outward from the square's interior at that midpoint is -y (downward).
        ox, oy = it._compute_turn_offset(self._square_ccw(), 0.125, magnitude=0.04)
        assert oy < 0
        assert abs(ox) < 1e-6

    def test_offset_magnitude_matches_argument(self):
        ox, oy = it._compute_turn_offset(self._square_ccw(), 0.125, magnitude=0.04)
        assert math.isclose(math.hypot(ox, oy), 0.04, rel_tol=0.01)

    def test_offset_outward_for_cw_polygon(self):
        # CW square starting from the same corner: (0.2,0.2) -> (0.2,0.5) -> (0.2,0.8) -> ...
        # frac=0.125 -> index 1 = midpoint of left edge (0.2, 0.5). Outward = -x (leftward).
        cw = [
            (0.2, 0.2), (0.2, 0.5), (0.2, 0.8),
            (0.5, 0.8), (0.8, 0.8), (0.8, 0.5),
            (0.8, 0.2), (0.5, 0.2),
        ]
        ox, oy = it._compute_turn_offset(cw, 0.125, magnitude=0.04)
        assert ox < 0
        assert abs(oy) < 1e-6


class TestLoadLovelyTurns:
    def _stub_pts(self):
        # Simple closed loop, enough points for offset computation to be meaningful.
        # Counter-clockwise circle approximation.
        n = 100
        out = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            out.append((0.5 + 0.4 * math.cos(theta), 0.5 + 0.4 * math.sin(theta)))
        return out

    def test_returns_empty_for_unknown_slug(self):
        assert it._load_lovely_turns('does_not_exist', self._stub_pts()) == []

    def test_spa_returns_expected_count_and_shape(self):
        # Spa's vendored file has 14 turn entries; 13 have a `marker`. The "Courbe Paul Frere"
        # entry has only start/end and is skipped.
        turns = it._load_lovely_turns('spa', self._stub_pts())
        assert len(turns) == 13
        for entry in turns:
            assert len(entry) == 5
            frac, lbl, name, ox, oy = entry
            assert 0.0 <= frac <= 1.0
            assert isinstance(lbl, str)
            assert isinstance(name, str) and name
            assert isinstance(ox, float)
            assert isinstance(oy, float)

    def test_labels_are_one_based_and_ordered_by_marker(self):
        turns = it._load_lovely_turns('spa', self._stub_pts())
        labels = [t[1] for t in turns]
        assert labels[0] == '1'
        assert labels[-1] == str(len(turns))
        fracs = [t[0] for t in turns]
        assert fracs == sorted(fracs)
