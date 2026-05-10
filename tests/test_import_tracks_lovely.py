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
