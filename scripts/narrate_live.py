#!/usr/bin/env python3
"""Live narrator CLI - generate narrated runs with real or fake LLM."""

import argparse
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.policy import choose_action
from tgn.autoplay.models import AutoplayConfig, StopReason
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.narrator import (
    NarratorService,
    narrate_run,
    render_narrated_run,
    create_builtin_registry,
    load_voice_packs,
    VoiceNotFoundError,
    DEFAULT_VOICE_ID,
    FakeNarratorClient,
    create_client_from_env,
)


def create_initial_state() -> GameState:
    """Create initial game state for narration."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="narrate-live",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
        },
    )


def list_voices(voice_pack_dir: Path | None = None) -> None:
    """List all available voice packs."""
    registry = create_builtin_registry()
    
    # Load local packs if directory provided
    if voice_pack_dir is not None:
        local_packs = load_voice_packs(voice_pack_dir)
        for pack in local_packs:
            registry.register(pack)
    
    voices = registry.list()
    
    print("Available voice packs:")
    print()
    
    for voice in voices:
        is_default = voice.name == DEFAULT_VOICE_ID
        marker = " [default]" if is_default else ""
        
        print(f"  {voice.name}{marker}")
        
        # Extract first line of description from instructions
        lines = voice.instructions.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('[') and not line.startswith('#'):
                # First non-header line is likely description
                print(f"    {line[:60]}...")
                break
        
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate narrated autoplay runs with pluggable voice packs"
    )
    
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help=f"Voice pack ID (default: {DEFAULT_VOICE_ID})"
    )
    
    parser.add_argument(
        "--voice-pack-dir",
        type=Path,
        default=None,
        help="Directory containing local voice packs"
    )
    
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voice packs and exit"
    )
    
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use fake narrator client (no API calls)"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout)"
    )
    
    args = parser.parse_args()
    
    # Handle --list-voices
    if args.list_voices:
        list_voices(args.voice_pack_dir)
        return 0
    
    # Build voice registry
    registry = create_builtin_registry()
    
    # Load local packs if directory provided
    if args.voice_pack_dir is not None:
        if not args.voice_pack_dir.is_dir():
            print(f"Error: Voice pack directory not found: {args.voice_pack_dir}", file=sys.stderr)
            return 1
        
        try:
            local_packs = load_voice_packs(args.voice_pack_dir)
            for pack in local_packs:
                registry.register(pack)
            print(f"Loaded {len(local_packs)} local voice pack(s)")
        except Exception as e:
            print(f"Error loading voice packs: {e}", file=sys.stderr)
            return 1
    
    # Determine voice ID
    voice_id = args.voice
    
    # Check environment variable
    if voice_id is None:
        voice_id = os.environ.get("TGN_NARRATOR_VOICE")
    
    # Use default
    if voice_id is None:
        voice_id = DEFAULT_VOICE_ID
    
    # Validate voice exists
    try:
        registry.get(voice_id)
    except VoiceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    print(f"Selected voice: {voice_id}")
    print()
    
    # Create client
    if args.fake:
        print("Using fake narrator client (no API calls)")
        client = FakeNarratorClient([
            "你从基地出发，沿着标记的路径向目标地点移动。十分钟后，你抵达了探索地点。",
            "你在探索地点仔细搜索，从废物中找到了 salvage ×2，携带在身上准备返回。",
            "你带着收获沿原路返回基地，将 salvage ×2 安全入库。",
        ])
    else:
        try:
            client = create_client_from_env()
            print(f"Using LLM client: {client.model}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Use --fake for offline testing without API credentials", file=sys.stderr)
            return 1
    
    print()
    
    # Run autoplay
    print("Running autoplay...")
    initial_state = create_initial_state()
    config = AutoplayConfig(max_decisions=10)
    
    autoplay_result = run_autoplay(
        initial_state,
        choose_action,
        config,
    )
    
    print(f"Autoplay complete: {autoplay_result.decisions} decisions, {autoplay_result.events} events")
    print(f"Stop reason: {autoplay_result.stop_reason}")
    print()
    
    # Check for rejected run
    if autoplay_result.stop_reason == StopReason.ACTION_REJECTED:
        print("Autoplay was rejected, no frames to narrate")
        return 0
    
    # Narrate frames
    print("Generating narration...")
    service = NarratorService(
        client=client,
        voice_id=voice_id,
        voice_registry=registry,
    )
    
    try:
        narration_result = narrate_run(autoplay_result, service)
    except Exception as e:
        print(f"Error during narration: {e}", file=sys.stderr)
        return 1
    
    print(f"Narration complete: {len(narration_result.narrated_frames)} frames")
    print()
    
    # Render output
    output_text = render_narrated_run(narration_result)
    
    # Verify game state unchanged
    hash_before = autoplay_result.final_state_hash
    hash_after = state_hash(autoplay_result.final_state.__dict__)
    
    if hash_before != hash_after:
        print("ERROR: Game state changed during narration!", file=sys.stderr)
        return 1
    
    # Write output
    if args.output:
        args.output.write_text(output_text, encoding='utf-8')
        print(f"Output written to: {args.output}")
    else:
        print("=" * 60)
        print(output_text)
        print("=" * 60)
    
    print()
    print(f"Final gameplay hash: {hash_after}")
    print()
    print("Done!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
