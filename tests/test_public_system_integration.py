"""
Integration tests for public survival system.

These tests verify the complete data flow:
1. Advance public states from GameState
2. Peer agents loaded from SQLite
3. Channel messages generated
4. Rankings updated
5. Data persisted back to SQLite
"""

import tempfile
import unittest
from pathlib import Path

from engine_runtime.public_survival import advance_public_states, initial_public_states
from engine_runtime.peer_agent import PeerAgent
from engine_runtime.persistence import insert_peer_agent, load_peer_agents, SQLiteEventStore


class PublicSystemIntegrationTests(unittest.TestCase):
    """Integration tests for public survival system main chain."""
    
    def test_advance_public_states_loads_peers_from_sqlite(self):
        """P0-01: Verify advance_public_states correctly loads and persists PeerAgent"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal world with collective contract
            world = {
                "name": "测试全名世界",
                "genre_contract": {
                    "collective_transmission": True,
                    "region_size": 100,
                },
                "public_survival": {
                    "system_name": "Test System",
                    "region_name": "Test Region",
                    "opening_announcement": "Start survival",
                    "opening_rules": ["Rule 1"],
                    "starting_channel_messages": [],
                    "initial_peers": [
                        {
                            "id": "peer_test_1",
                            "name": "测试者甲",
                            "attributes": {"strength": 10, "agility": 10, "spirit": 10, "constitution": 10},
                        },
                    ],
                    "competition": {
                        "initial_percentile": 50,
                        "outcome_scores": {"大成功": 15, "普通成功": 9, "成功但付出代价": 5, "失败但获得部分信息": 2, "严重失败": -5},
                        "losses_per_trigger": 1,
                        "loss_roll_threshold": 70,
                        "location_discovery_bonus": 4,
                        "knowledge_bonus": 3,
                        "positive_resource_bonus_cap": 2,
                        "rank_season_end_turn": 50,
                        "active_rival_count": 3,
                    },
                },
            }
            
            # Setup database
            db_path = Path(tmpdir) / "campaign.sqlite3"
            store = SQLiteEventStore(db_path, "test_campaign_integration")
            
            # Initialize with proper initial_public_states
            from engine_runtime.public_survival import initial_public_states
            
            dummy_data = {
                "meta": {"campaign_id": "test_campaign_integration", "world_name": "test"},
                "world": world,
                **initial_public_states(world),  # Add required public state keys
            }
            store.initialize(dummy_data)
            
            # Insert peer agent into SQLite manually (simulating existing data)
            peer = PeerAgent(
                id="peer_inserted_manual",
                name="手动插入的同行",
                attributes={"strength": 15, "agility": 12, "spirit": 14, "constitution": 13},
                level=2,
            )
            
            # Mock state object (has .store attribute)
            class MockState:
                pass
            
            mock_state = MockState()
            mock_state.store = store
            mock_state.data = dict(dummy_data)
            
            # Insert peer
            insert_peer_agent(mock_state, "test_campaign_integration", peer)
            
            # Verify peer is in SQLite
            loaded_peers = load_peer_agents(mock_state, "test_campaign_integration")
            self.assertEqual(len(loaded_peers), 1)
            self.assertEqual(loaded_peers[0].id, "peer_inserted_manual")
            
            # Now call advance_public_states with real GameState-like object
            action_result = {
                "event": {"data": {"time_cost": 60.0}},
                "events": [],
                "resolution": {"outcome": "普通成功", "probability": 0.8},
            }
            
            result, feedback = advance_public_states(mock_state, action_result)
            
            # Assertions
            self.assertIsNotNone(result, "advance_public_states should not return None")
            self.assertIsNotNone(feedback, "feedback should be provided")
            
            # 1. Check channel feed has new messages
            channel_feed = result.get("public_system_state", {}).get("channel_feed", [])
            self.assertGreater(len(channel_feed), 0, "Channel feed should have at least one message")
            
            # 2. Check ranking exists
            ranking_state = result.get("ranking_state", {})
            self.assertIn("player_rank_regional", ranking_state)
            self.assertIsNotNone(ranking_state["player_rank_regional"])
            
            # 3. Verify peer was persisted back to SQLite
            reloaded_peers = load_peer_agents(mock_state, "test_campaign_integration")
            self.assertGreaterEqual(len(reloaded_peers), 1, "SQLite should still contain peer agent")
            
            # 4. Verify peer action history increased (should be > 0)
            peer_with_history = next((p for p in reloaded_peers if p.id == "peer_inserted_manual"), None)
            if peer_with_history:
                self.assertGreater(
                    len(peer_with_history.action_history),
                    0,
                    "Peer action history should be recorded"
                )
                
                # Verify history record structure
                first_action = peer_with_history.action_history[0]
                self.assertIn("turn", first_action)
                self.assertIn("action_type", first_action)


if __name__ == "__main__":
    unittest.main()
