"""Tests for local voice pack loader."""

import json
import pytest
from pathlib import Path
from tgn.narrator.voice_loader import (
    load_voice_pack,
    load_voice_packs,
    validate_voice_id,
    InvalidVoicePackError,
    VoicePackManifestError,
    VoicePackSecurityError,
)
from tgn.narrator.voice import DuplicateVoiceError, create_builtin_registry


class TestVoiceIdValidation:
    """Tests for voice ID validation."""
    
    def test_valid_voice_id_simple(self):
        """Simple lowercase ID is valid."""
        validate_voice_id("myvoice")
    
    def test_valid_voice_id_with_numbers(self):
        """ID with numbers is valid."""
        validate_voice_id("voice123")
    
    def test_valid_voice_id_with_underscore(self):
        """ID with underscore is valid."""
        validate_voice_id("my_voice")
    
    def test_valid_voice_id_with_hyphen(self):
        """ID with hyphen is valid."""
        validate_voice_id("my-voice")
    
    def test_valid_voice_id_starting_with_number(self):
        """ID starting with number is valid."""
        validate_voice_id("123voice")
    
    def test_invalid_voice_id_empty(self):
        """Empty ID is invalid."""
        with pytest.raises(InvalidVoicePackError, match="cannot be empty"):
            validate_voice_id("")
    
    def test_invalid_voice_id_uppercase(self):
        """Uppercase ID is invalid."""
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            validate_voice_id("MyVoice")
    
    def test_invalid_voice_id_spaces(self):
        """ID with spaces is invalid."""
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            validate_voice_id("my voice")
    
    def test_invalid_voice_id_special_chars(self):
        """ID with special characters is invalid."""
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            validate_voice_id("my@voice")
    
    def test_invalid_voice_id_starts_with_hyphen(self):
        """ID starting with hyphen is invalid."""
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            validate_voice_id("-myvoice")
    
    def test_invalid_voice_id_starts_with_underscore(self):
        """ID starting with underscore is invalid."""
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            validate_voice_id("_myvoice")
    
    def test_invalid_voice_id_too_long(self):
        """ID exceeding max length is invalid."""
        long_id = "a" * 65
        with pytest.raises(InvalidVoicePackError, match="too long"):
            validate_voice_id(long_id)


class TestLoadVoicePack:
    """Tests for loading voice packs."""
    
    @pytest.fixture
    def valid_pack_dir(self, tmp_path):
        """Create a valid voice pack directory."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        # Create manifest
        manifest = {
            "id": "test_voice",
            "display_name": "Test Voice",
            "language": "zh-CN",
            "version": 1,
            "description": "A test voice pack",
            "instructions_file": "instructions.md",
            "examples_file": "examples.md"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        # Create instructions
        instructions = "[WRITING VOICE — TEST]\n\nTest instructions here."
        with open(pack_dir / "instructions.md", 'w', encoding='utf-8') as f:
            f.write(instructions)
        
        # Create examples
        examples = "[STYLE EXAMPLES — NOT WORLD FACTS]\n\nExample text."
        with open(pack_dir / "examples.md", 'w', encoding='utf-8') as f:
            f.write(examples)
        
        return pack_dir
    
    def test_load_valid_pack(self, valid_pack_dir):
        """Can load a valid voice pack."""
        profile = load_voice_pack(valid_pack_dir)
        
        assert profile.name == "test_voice"
        assert "Test instructions" in profile.instructions
    
    def test_load_pack_instructions_utf8(self, valid_pack_dir):
        """Instructions are loaded as UTF-8."""
        # Add Chinese characters to instructions
        instructions_path = valid_pack_dir / "instructions.md"
        with open(instructions_path, 'w', encoding='utf-8') as f:
            f.write("测试中文指令")
        
        profile = load_voice_pack(valid_pack_dir)
        assert "测试中文指令" in profile.instructions
    
    def test_load_pack_examples_optional(self, tmp_path):
        """Examples file is optional."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "test_voice",
            "instructions_file": "instructions.md"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with open(pack_dir / "instructions.md", 'w', encoding='utf-8') as f:
            f.write("Instructions")
        
        profile = load_voice_pack(pack_dir)
        assert profile.name == "test_voice"
    
    def test_missing_manifest_rejected(self, tmp_path):
        """Pack without manifest.json is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        with open(pack_dir / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(VoicePackManifestError, match="manifest.json not found"):
            load_voice_pack(pack_dir)
    
    def test_malformed_manifest_rejected(self, tmp_path):
        """Malformed manifest.json is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        with open(pack_dir / "manifest.json", 'w') as f:
            f.write("{ invalid json")
        
        with open(pack_dir / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(VoicePackManifestError, match="malformed"):
            load_voice_pack(pack_dir)
    
    def test_missing_instructions_rejected(self, tmp_path):
        """Pack without instructions file is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "test_voice",
            "instructions_file": "instructions.md"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with pytest.raises(InvalidVoicePackError, match="Instructions file not found"):
            load_voice_pack(pack_dir)
    
    def test_missing_instructions_field_rejected(self, tmp_path):
        """Manifest without instructions_file field is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "test_voice"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with open(pack_dir / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(VoicePackManifestError, match="missing required field"):
            load_voice_pack(pack_dir)
    
    def test_invalid_voice_id_in_manifest_rejected(self, tmp_path):
        """Manifest with invalid voice ID is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "Invalid Voice",  # Spaces not allowed
            "instructions_file": "instructions.md"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with open(pack_dir / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(InvalidVoicePackError, match="invalid"):
            load_voice_pack(pack_dir)
    
    def test_path_traversal_instructions_rejected(self, tmp_path):
        """Path traversal in instructions_file is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "test_voice",
            "instructions_file": "../../secret.txt"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with pytest.raises(VoicePackSecurityError, match="Path traversal"):
            load_voice_pack(pack_dir)
    
    def test_path_traversal_examples_rejected(self, tmp_path):
        """Path traversal in examples_file is rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        manifest = {
            "id": "test_voice",
            "instructions_file": "instructions.md",
            "examples_file": "../../../etc/passwd"
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with open(pack_dir / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(VoicePackSecurityError, match="Path traversal"):
            load_voice_pack(pack_dir)
    
    def test_absolute_path_rejected(self, tmp_path):
        """Absolute paths are rejected."""
        pack_dir = tmp_path / "test_voice"
        pack_dir.mkdir()
        
        # Construct an absolute path that works on both Windows and POSIX
        outside_path = (tmp_path.parent / "outside.md").resolve()
        assert outside_path.is_absolute()
        
        manifest = {
            "id": "test_voice",
            "instructions_file": str(outside_path)
        }
        
        with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with pytest.raises(VoicePackSecurityError, match="Absolute paths"):
            load_voice_pack(pack_dir)
    
    def test_local_pack_cannot_override_builtin(self, valid_pack_dir):
        """Local pack cannot override built-in voice IDs."""
        # Change manifest to use built-in voice ID
        manifest_path = valid_pack_dir / "manifest.json"
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        manifest["id"] = "cablecar_survival"
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        # Load the pack
        profile = load_voice_pack(valid_pack_dir)
        
        # Try to register it in built-in registry
        registry = create_builtin_registry()
        
        with pytest.raises(DuplicateVoiceError, match="already registered"):
            registry.register(profile)


class TestLoadVoicePacks:
    """Tests for loading multiple voice packs."""
    
    @pytest.fixture
    def voice_packs_root(self, tmp_path):
        """Create a root directory with multiple voice packs."""
        root = tmp_path / "voice_packs"
        root.mkdir()
        
        # Create two valid packs
        for name in ["voice_a", "voice_b"]:
            pack_dir = root / name
            pack_dir.mkdir()
            
            manifest = {
                "id": name,
                "instructions_file": "instructions.md"
            }
            
            with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
                json.dump(manifest, f)
            
            with open(pack_dir / "instructions.md", 'w', encoding='utf-8') as f:
                f.write(f"Instructions for {name}")
        
        return root
    
    def test_load_multiple_packs(self, voice_packs_root):
        """Can load multiple voice packs."""
        profiles = load_voice_packs(voice_packs_root)
        
        assert len(profiles) == 2
        
        names = [p.name for p in profiles]
        assert "voice_a" in names
        assert "voice_b" in names
    
    def test_load_packs_deterministic_order(self, voice_packs_root):
        """load_voice_packs returns deterministic order."""
        profiles1 = load_voice_packs(voice_packs_root)
        profiles2 = load_voice_packs(voice_packs_root)
        
        assert profiles1 == profiles2
    
    def test_load_packs_skips_hidden_dirs(self, voice_packs_root):
        """load_voice_packs skips hidden directories."""
        # Create hidden directory
        hidden = voice_packs_root / ".hidden_voice"
        hidden.mkdir()
        
        manifest = {
            "id": "hidden_voice",
            "instructions_file": "instructions.md"
        }
        
        with open(hidden / "manifest.json", 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        
        with open(hidden / "instructions.md", 'w') as f:
            f.write("Hidden")
        
        profiles = load_voice_packs(voice_packs_root)
        
        # Should only load the two non-hidden packs
        assert len(profiles) == 2
        names = [p.name for p in profiles]
        assert "hidden_voice" not in names
    
    def test_load_packs_invalid_dir(self, tmp_path):
        """Invalid root directory raises error."""
        invalid_dir = tmp_path / "nonexistent"
        
        with pytest.raises(InvalidVoicePackError, match="Root directory not found"):
            load_voice_packs(invalid_dir)
    
    def test_load_packs_one_invalid_fails_all(self, voice_packs_root):
        """One invalid pack causes entire load to fail."""
        # Create invalid pack
        invalid_pack = voice_packs_root / "invalid_voice"
        invalid_pack.mkdir()
        
        # Missing manifest
        with open(invalid_pack / "instructions.md", 'w') as f:
            f.write("Instructions")
        
        with pytest.raises(InvalidVoicePackError, match="Failed to load voice pack"):
            load_voice_packs(voice_packs_root)
