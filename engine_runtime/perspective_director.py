"""Perspective Director - decides when to show off-screen player POV."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


def rounded(value: float) -> float:
    """Helper function to round float values."""
    return round(float(value), 2)


@dataclass
class PerspectiveCandidate:
    """Potential cutaway target with convergence score."""
    peer_id: str
    peer_name: str
    convergence_score: float
    motivation: str
    location_name: str
    time_constraint: int
    resource_status: Dict[str, Any]
    narrative_importance: float


class PerspectiveDirector:
    """Lightweight director calculating convergence scores for potential cutaways."""
    
    THRESHOLDS = {
        "background_trigger": 0.50,
        "cutaway_eligible": 0.70,
        "guaranteed_cutaway": 0.85,
    }
    
    MAX_CONCURRENT_THREADS = 2
    MIN_GAP_BETWEEN_SAME_CHARACTER = 3
    
    def __init__(self, engine):
        self.engine = engine
        self.last_triggered_turn = -10
        self.active_threads: Dict[str, Any] = {}
    
    def should_trigger(self, current_turn: int) -> bool:
        """Check if we should evaluate cutaways this turn."""
        # Cooldown check: never consecutive turns
        if current_turn - self.last_triggered_turn <= 1:
            return False
        
        # Concurrent threads limit
        meta = self.engine.state.meta
        perspective_metrics = meta.get("perspective_metrics", {})
        active_count = perspective_metrics.get("active_threads", 0)
        
        if active_count >= self.MAX_CONCURRENT_THREADS:
            return False
        
        return True
    
    def evaluate_candidates(self) -> List[PerspectiveCandidate]:
        """Find high-convergence peer players."""
        state = self.engine.state
        protagonist_location = state.meta.get("current_location", "")
        
        candidates = []
        peer_players = state.store.query_entities(
            campaign_id=state.store.campaign_id,
            entity_type="peer_players"
        )
        
        for peer in peer_players:
            if not isinstance(peer, dict):
                continue
            
            peer_id = peer.get("id", "")
            
            # Skip if shown recently enough
            last_shown_turn = self._get_last_cutaway_turn(peer_id)
            if last_shown_turn and (state.current_turn - last_shown_turn) < self.MIN_GAP_BETWEEN_SAME_CHARACTER:
                continue
            
            # Calculate convergence score
            convergence = self._calculate_convergence_score(
                protagonist_location=protagonist_location,
                peer_location=peer.get("location", ""),
                peer_inventory=peer.get("inventory", {}),
                protagonist_inventory=state.player.get("inventory", {}),
                recent_events=state.event_history()[-10:],
                peer_personality=peer.get("personality", {}),
            )
            
            if convergence >= self.THRESHOLDS["cutaway_eligible"]:
                candidates.append(PerspectiveCandidate(
                    peer_id=peer_id,
                    peer_name=peer.get("name", "Unknown Player"),
                    convergence_score=convergence,
                    motivation=self._infer_motivation(peer),
                    location_name=peer.get("location_name", peer.get("location")),
                    time_constraint=self._estimate_wait_time(peer),
                    resource_status=peer.get("inventory", {}).get("resources", {}),
                    narrative_importance=peer.get("rarity_score", 50),
                ))
        
        return sorted(candidates, key=lambda c: c.convergence_score, reverse=True)[:2]
    
    def _calculate_convergence_score(
        self,
        protagonist_location: str,
        peer_location: str,
        peer_inventory: Mapping[str, Any],
        protagonist_inventory: Mapping[str, Any],
        recent_events: List[Mapping[str, Any]],
        peer_personality: Mapping[str, Any],
    ) -> float:
        """Calculate convergence score (0-100)."""
        from engine_runtime.calculators import rounded as calc_rounded
        from engine_runtime.models import state
        
        score = 0.0
        current_turn = self.engine.state.current_turn
        
        # Physical proximity (+30 same location, +15 adjacent)
        if peer_location == protagonist_location:
            score += 30.0
        elif self._are_adjacent_locations(peer_location, protagonist_location):
            score += 15.0
        
        # Resource conflict (+25)
        if self._has_resource_conflict(peer_inventory, protagonist_inventory):
            score += 25.0
        
        # Common threat (+15)
        if self._faces_common_threat(peer_location, recent_events):
            score += 15.0
        
        # Temporal alignment (+10)
        peer_activity_turn = peer_personality.get("last_active_turn", 0)
        if abs(current_turn - peer_activity_turn) <= 1:
            score += 10.0
        
        # Recent event overlap (+10)
        if self._shared_recent_events(peer_location, recent_events):
            score += 10.0
        
        return min(100.0, calc_rounded(score))
    
    def _infer_motivation(self, peer: Mapping[str, Any]) -> str:
        """Infer peer's goal from inventory/actions."""
        inventory = peer.get("inventory", {})
        goals = []
        
        if inventory.get("resources", {}).get("ammo", 0) < 5:
            goals.append("寻找弹药补充")
        if inventory.get("equipment", {}).get("weapon_durability", 0) < 20:
            goals.append("修复装备")
        if peer.get("goal") in ["resource_search", "exploration"]:
            goals.append(f"在{peer.get('location')}搜集资源")
        
        return f"正在：{'，'.join(goals)}" if goals else "常规生存活动"
    
    def _estimate_wait_time(self, peer: Mapping[str, Any]) -> int:
        """Estimate turns until next major action."""
        schedule = peer.get("schedule", {})
        current_period = self.engine.state.meta.get("time_of_day", "")
        
        wait_times = {"清晨": 60, "白天": 120, "黄昏": 90, "夜晚": 180}
        return wait_times.get(current_period, 120)
    
    def generate_cutaway_package(self, candidate: PerspectiveCandidate) -> Dict[str, Any]:
        """Generate NarrativePackage-compatible cutaway fragment."""
        return {
            "id": f"cutaway_{candidate.peer_id}_{self.engine.state.current_turn}",
            "viewpoint_actor": candidate.peer_id,
            "narrative_function": "approaching_collision" if candidate.convergence_score > 0.85 else "general_off_screen_action",
            "verified_events": [f"{candidate.peer_name} 正在{candidate.motivation}"],
            "reader_reveal": [
                f"{candidate.peer_name} 是{candidate.location_name}区域的求生者",
                f"他的队伍可能接近主角活动区（收敛度评分：{candidate.convergence_score:.2f}）",
            ],
            "forbidden_reveal": ["精确坐标", "精确碰面时间", "所有队员完整能力", "伏击位置"],
            "protagonist_knowledge_delta": [],
            "reader_knowledge_delta": [
                f"{candidate.peer_id}_exists",
                f"{candidate.peer_id}_group_is_nearby" if candidate.convergence_score > 0.8 else None,
            ],
        }
    
    def _get_last_cutaway_turn(self, peer_id: str) -> int:
        """Get last time this peer was shown in cutaway."""
        meta = self.engine.state.meta
        cutaway_contexts = meta.get("cutaway_contexts", {})
        for ctx in cutaway_contexts.values():
            if ctx.get("reader_id") == peer_id and ctx.get("status") == "ended":
                return ctx.get("ended_turn", 0)
        return 0
    
    def _are_adjacent_locations(self, loc1: str, loc2: str) -> bool:
        """Check if locations are adjacent (simplified logic)."""
        # Placeholder - implement based on actual world map
        return False
    
    def _has_resource_conflict(self, inv1: Mapping, inv2: Mapping) -> bool:
        """Check if both parties want same resources."""
        res1 = set(inv1.get("resources", {}).keys())
        res2 = set(inv2.get("resources", {}).keys())
        return len(res1 & res2) > 0
    
    def _faces_common_threat(self, location: str, recent_events: List) -> bool:
        """Check if peer faces same threats as protagonist."""
        # Placeholder - could check monster densities, disaster warnings
        return False
    
    def _shared_recent_events(self, location: str, recent_events: List) -> bool:
        """Check if both participated in similar events."""
        # Placeholder - could compare location-based events
        return False
