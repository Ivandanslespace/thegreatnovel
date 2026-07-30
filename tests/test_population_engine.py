"""Population engine regression tests (3 essential tests)."""
import unittest
import sqlite3
from pathlib import Path

from engine_runtime.ranking_engine import (
    calculate_cdf_percentile,
    calculate_dimension_scores,
    convert_percentile_to_rank,
)
from engine_runtime.public_survival import initial_public_states


class TestPopulationEngine(unittest.TestCase):

    def test_first_action_stays_near_50th_percentile(self):
        """Normal action with empty peer pool must NOT jump to top 20%."""
        action = {"action_type": "EXPLORATION", "resources_obtained": {"water": 2}}
        dims = calculate_dimension_scores(action)
        pct = calculate_cdf_percentile(dims, [])
        self.assertAlmostEqual(pct, 50.0, delta=1.0,
                               msg=f"Expected ~50th percentile, got {pct}")
        rank = convert_percentile_to_rank(pct, 1000)
        self.assertGreater(rank, 200,
                           msg=f"Rank {rank} is in top 20% — the #1 bug")

    def test_peer_agents_exist_in_sqlite(self):
        """Migrated saves must have 4 peer_players in SQLite."""
        for name in ("灰烬列车", "锈铁方舟"):
            db = Path(__file__).resolve().parent.parent / "saves" / name / "campaign.sqlite3"
            if not db.exists():
                self.skipTest(f"{name} DB not found")
            conn = sqlite3.connect(str(db))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM peer_players")
            count = cur.fetchone()[0]
            conn.close()
            self.assertEqual(count, 4, f"{name}: expected 4 peers, got {count}")

    def test_initial_channel_feed_has_messages(self):
        """New collective world must produce non-empty channel_feed."""
        world = {
            "genre_contract": {
                "collective_transmission": True,
                "region_size": 100,
                "public_system": {"regional_chat": True, "announcements": True},
            },
            "public_survival": {
                "competition": {
                    "initial_percentile": 0, "active_rival_count": 2,
                    "outcome_scores": {"普通成功": 15},
                    "location_discovery_bonus": 10, "knowledge_bonus": 5,
                    "positive_resource_bonus_cap": 20, "percentile_per_score": 0.5,
                    "loss_roll_threshold": 85, "losses_per_trigger": 1,
                    "rank_season_end_turn": 100,
                },
                "initial_peers": [
                    {"id": "p1", "name": "A"}, {"id": "p2", "name": "B"},
                ],
                "starting_channel_messages": [
                    {"sender": "A", "message": "hello"},
                ],
            },
        }
        states = initial_public_states(world)
        feed = states["public_system_state"].get("channel_feed", [])
        self.assertGreater(len(feed), 0, "channel_feed is empty after init")


if __name__ == "__main__":
    unittest.main(verbosity=2)
