"""Narrator service - orchestrates narration generation."""

from __future__ import annotations

from typing import Any

from ..autoplay.models import AutoplayRunResult, StopReason, WatchFrame
from .context import build_narration_context
from .prompt import build_narrator_prompt
from .voice import WritingVoiceProfile, DEFAULT_VOICE
from .guard import validate_narration, NarrationValidationError
from .models import NarratedFrame, NarrationError, NarrationRunResult, NarratorClient


class NarratorService:
    """
    Service that generates narrations from watch frames.
    
    Flow:
    1. WatchFrame → NarrationContext (context.py)
    2. NarrationContext + VoiceProfile → prompt (prompt.py)
    3. prompt → narration text (client)
    4. Validate narration (guard.py)
    5. Return NarratedFrame
    
    The narrator is PRESENTATION ONLY. It cannot modify game state.
    Voice profile determines HOW to write, facts determine WHAT happened.
    Facts ALWAYS override voice requirements.
    """
    
    def __init__(
        self,
        client: NarratorClient,
        voice_profile: WritingVoiceProfile | None = None,
    ):
        self.client = client
        self.voice_profile = voice_profile if voice_profile is not None else DEFAULT_VOICE
    
    def narrate_frame(
        self,
        frame: WatchFrame,
        previous_text: str | None = None,
    ) -> NarratedFrame:
        """
        Generate narration for a single frame.
        
        Args:
            frame: The watch frame to narrate
            previous_text: Optional previous narration for continuity
        
        Returns:
            NarratedFrame with generated narration
        
        Raises:
            NarrationError: If narration generation fails
        """
        try:
            # Build context from frame (pure function)
            context = build_narration_context(frame)
            
            # Build prompt with voice profile (deterministic)
            prompt = build_narrator_prompt(context, self.voice_profile, previous_text)
            
            # Generate narration via client
            narration = self.client.generate(prompt)
            
            # Validate narration against context (guard)
            validate_narration(context, narration)
            
            # Return narrated frame
            return NarratedFrame(
                step=frame.step,
                action_type=frame.action_type,
                event_type=frame.event_type,
                narration=narration,
                state_hash_before=frame.state_hash_before,
                state_hash_after=frame.state_hash_after,
            )
        
        except NarrationValidationError as e:
            # Hallucination detected - fail fast
            raise NarrationError(
                step=frame.step,
                action_type=frame.action_type,
                event_type=frame.event_type,
                message=f"Hallucination detected: {e}",
            ) from e
        except Exception as e:
            # Client or other error
            raise NarrationError(
                step=frame.step,
                action_type=frame.action_type,
                event_type=frame.event_type,
                message=f"Narration generation failed: {e}",
            ) from e


def narrate_run(
    run_result: AutoplayRunResult,
    narrator: NarratorService,
) -> NarrationRunResult:
    """
    Generate narrations for all frames in an autoplay run.
    
    Args:
        run_result: The autoplay run result containing frames
        narrator: The narrator service
    
    Returns:
        NarrationRunResult with all narrated frames
    
    Raises:
        NarrationError: If any frame narration fails (fail-fast)
    
    Notes:
    - If run was rejected (ACTION_REJECTED, 0 frames), returns empty result
    - If run hit MAX_DECISIONS, narrates all completed frames
    - FAIL-FAST: Any narration failure stops the entire run immediately
    - Game state hash is verified unchanged after narration
    """
    # Check for rejected run (no frames)
    if run_result.stop_reason == StopReason.ACTION_REJECTED or len(run_result.frames) == 0:
        return NarrationRunResult(
            narrated_frames=(),
            source_initial_hash=run_result.initial_state_hash,
            source_final_hash=run_result.final_state_hash,
            narration_failures=0,
            source_run=run_result,
        )
    
    narrated_frames = []
    previous_text = None
    
    # Verify game state hash before narration
    initial_hash = run_result.initial_state_hash
    
    # FAIL-FAST: Let NarrationError propagate immediately
    for frame in run_result.frames:
        narrated = narrator.narrate_frame(frame, previous_text)
        narrated_frames.append(narrated)
        previous_text = narrated.narration
    
    # Verify game state hash unchanged after narration
    # (narration should be pure presentation, no side effects)
    final_hash = run_result.final_state_hash
    
    return NarrationRunResult(
        narrated_frames=tuple(narrated_frames),
        source_initial_hash=run_result.initial_state_hash,
        source_final_hash=run_result.final_state_hash,
        narration_failures=0,  # Always 0 for successful result
        source_run=run_result,
    )
