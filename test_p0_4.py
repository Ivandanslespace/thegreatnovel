#!/usr/bin/env python3
"""Simple P0-4 fix validation."""

from tools.create_save import parse_genre_contract_choice

print("测试 1: Genre 3 (solo_survival) 不包含 disaster_cycle...")
genre3 = parse_genre_contract_choice("3", "test")
assert genre3['id'] == 'solo_survival'
assert 'disaster_cycle' not in genre3.get('requirements', []), "Genre 3 should NOT require disaster_cycle"
assert 'exploration_method' in genre3.get('requirements', []), "Genre 3 requires exploration_method"
print(f"✓ Genre 3 requirements: {genre3['requirements']}")
print()

print("测试 2: Genre 4 (ship_no_disaster) 使用 vehicle_base/navigation_tools...")
genre4 = parse_genre_contract_choice("4", "test")
assert genre4['id'] == 'ship_no_disaster'
assert 'vehicle_base' in genre4.get('requirements', []), "Genre 4 requires vehicle_base"
assert 'navigation_tools' in genre4.get('requirements', []), "Genre 4 requires navigation_tools"
assert genre4['collective_transmission'] == False, "Genre 4 should NOT have collective_transmission"
print(f"✓ Genre 4 requirements: {genre4['requirements']}")
print(f"  collective_transmission: {genre4['collective_transmission']}")
print()

print("测试 3: Genre 1 (mass_system_survival) 仍然要求 disaster_cycle...")
genre1 = parse_genre_contract_choice("1", "test")
assert genre1['id'] == 'mass_system_survival'
assert 'disaster_cycle' in genre1.get('requirements', []), "Genre 1 requires disaster_cycle"
assert 'disaster_type' in genre1.get('requirements', []), "Genre 1 requires disaster_type"
print(f"✓ Genre 1 requirements: {genre1['requirements']}")
print()

# Test cycle_days=None handling
from tools.create_save import first_number

print("测试 4: disaster_cycle=None 处理...")
result = first_number("")
assert result is None, f"Expected None for empty string, got {result}"
result = first_number(None)
assert result is None, f"Expected None for None, got {result}"
result = first_number("每 7 天")
assert result == 7, f"Expected 7, got {result}"
print(f"  first_number('') = {result!r}")
print(f"  ✓ cycle_days can be None/null")
print()

print("=" * 60)
print("✓ 所有 P0-4 核心修复验证通过！")
print("- Genre 3 (solo_survival): no disaster_cycle requirement")
print("- Genre 4 (ship_no_disaster): uses vehicle_base + navigation_tools")
print("- Genre 1 (mass_system_survival): still requires disasters")
print("- disaster_cycle can be None")
print("=" * 60)
