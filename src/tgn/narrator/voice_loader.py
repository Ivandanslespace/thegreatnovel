"""Local voice pack loader with security validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Tuple

from .voice import WritingVoiceProfile, DuplicateVoiceError


# Voice ID validation pattern
VOICE_ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
MAX_VOICE_ID_LENGTH = 64


class InvalidVoicePackError(Exception):
    """Raised when a voice pack fails validation."""
    pass


class VoicePackManifestError(InvalidVoicePackError):
    """Raised when manifest.json is missing or malformed."""
    pass


class VoicePackSecurityError(InvalidVoicePackError):
    """Raised when a voice pack attempts path traversal or other security violations."""
    pass


def validate_voice_id(voice_id: str) -> None:
    """
    Validate voice ID format.
    
    Must match: [a-z0-9][a-z0-9_-]*
    Max length: 64 characters
    
    Raises InvalidVoicePackError if invalid.
    """
    if not voice_id:
        raise InvalidVoicePackError("Voice ID cannot be empty")
    
    if len(voice_id) > MAX_VOICE_ID_LENGTH:
        raise InvalidVoicePackError(
            f"Voice ID too long: {len(voice_id)} > {MAX_VOICE_ID_LENGTH}"
        )
    
    if not VOICE_ID_PATTERN.match(voice_id):
        raise InvalidVoicePackError(
            f"Voice ID '{voice_id}' invalid. "
            f"Must match pattern: [a-z0-9][a-z0-9_-]*"
        )


def validate_file_path(pack_dir: Path, file_path: str) -> Path:
    """
    Validate that a file path doesn't escape the pack directory.
    
    Prevents path traversal attacks like "../../secret.txt".
    
    Raises VoicePackSecurityError if path traversal detected.
    """
    # Normalize the path
    normalized = Path(file_path)
    
    # Check for absolute paths
    if normalized.is_absolute():
        raise VoicePackSecurityError(
            f"Absolute paths not allowed: {file_path}"
        )
    
    # Resolve relative to pack_dir
    resolved = (pack_dir / normalized).resolve()
    
    # Ensure it's still within pack_dir
    try:
        resolved.relative_to(pack_dir.resolve())
    except ValueError:
        raise VoicePackSecurityError(
            f"Path traversal detected: {file_path} escapes pack directory"
        )
    
    return resolved


def load_voice_pack(pack_dir: Path) -> WritingVoiceProfile:
    """
    Load a voice pack from a directory.
    
    Expected structure:
    - manifest.json (required)
    - instructions.md (required, referenced by manifest)
    - examples.md (optional, referenced by manifest)
    
    Security:
    - No Python code execution
    - Path traversal protection
    - Voice ID validation
    
    Raises:
        VoicePackManifestError: If manifest missing or malformed
        VoicePackSecurityError: If path traversal detected
        InvalidVoicePackError: If validation fails
    """
    pack_dir = Path(pack_dir).resolve()
    
    if not pack_dir.is_dir():
        raise InvalidVoicePackError(f"Pack directory not found: {pack_dir}")
    
    # Load manifest
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        raise VoicePackManifestError(f"manifest.json not found in {pack_dir}")
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        raise VoicePackManifestError(f"manifest.json malformed: {e}")
    
    # Validate required fields
    required_fields = ['id', 'instructions_file']
    for field in required_fields:
        if field not in manifest:
            raise VoicePackManifestError(
                f"manifest.json missing required field: {field}"
            )
    
    voice_id = manifest['id']
    
    # Validate voice ID
    validate_voice_id(voice_id)
    
    # Load instructions (required)
    instructions_file = manifest['instructions_file']
    instructions_path = validate_file_path(pack_dir, instructions_file)
    
    if not instructions_path.is_file():
        raise InvalidVoicePackError(
            f"Instructions file not found: {instructions_file}"
        )
    
    try:
        with open(instructions_path, 'r', encoding='utf-8') as f:
            instructions = f.read()
    except Exception as e:
        raise InvalidVoicePackError(
            f"Failed to read instructions file: {e}"
        )
    
    # Load examples (optional)
    examples = ()
    if 'examples_file' in manifest:
        examples_file = manifest['examples_file']
        examples_path = validate_file_path(pack_dir, examples_file)
        
        if not examples_path.is_file():
            raise InvalidVoicePackError(
                f"Examples file not found: {examples_file}"
            )
        
        try:
            with open(examples_path, 'r', encoding='utf-8') as f:
                examples_content = f.read()
            examples = (examples_content,)
        except Exception as e:
            raise InvalidVoicePackError(
                f"Failed to read examples file: {e}"
            )
    
    # Extract metadata (optional)
    display_name = manifest.get('display_name', voice_id)
    description = manifest.get('description', '')
    language = manifest.get('language', 'zh-CN')
    version = manifest.get('version', 1)
    
    # Create voice profile
    # Note: WritingVoiceProfile currently only has name and instructions
    # We could extend it later to include metadata, but for now we keep it simple
    profile = WritingVoiceProfile(
        name=voice_id,
        instructions=instructions,
    )
    
    return profile


def load_voice_packs(root_dir: Path) -> Tuple[WritingVoiceProfile, ...]:
    """
    Load all voice packs from subdirectories of root_dir.
    
    Each subdirectory should contain a valid voice pack.
    
    Returns:
        Tuple of loaded voice profiles (deterministic order)
    
    Raises:
        InvalidVoicePackError: If any pack fails validation
    """
    root_dir = Path(root_dir).resolve()
    
    if not root_dir.is_dir():
        raise InvalidVoicePackError(f"Root directory not found: {root_dir}")
    
    profiles = []
    
    # Iterate subdirectories in sorted order for determinism
    for pack_dir in sorted(root_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        
        # Skip hidden directories
        if pack_dir.name.startswith('.'):
            continue
        
        try:
            profile = load_voice_pack(pack_dir)
            profiles.append(profile)
        except InvalidVoicePackError as e:
            # Re-raise with pack directory context
            raise InvalidVoicePackError(
                f"Failed to load voice pack from {pack_dir.name}: {e}"
            )
    
    return tuple(profiles)
