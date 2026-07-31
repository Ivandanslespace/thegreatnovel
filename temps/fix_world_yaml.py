import yaml

# Load the deeply nested YAML
with open('saves/灰烬列车/world.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Recursively unwrap until we get to actual content
def unwrap(d):
    while isinstance(d, dict):
        keys = list(d.keys())
        if len(keys) != 1:
            break
        k, v = keys[0], d[keys[0]]
        if not isinstance(v, dict):
            return d
        d = v
    return d

actual_data = unwrap(data)
print("name:", actual_data.get('name'))
print("theme:", actual_data.get('theme'))

# Find player_talent - it should be alongside the deeply nested world in the original structure
# The original has {world: {world:...}, player_talent: {...}} somewhere up the tree
def find_player_talent(obj):
    if isinstance(obj, dict):
        if 'player_talent' in obj and 'world' in obj:
            # Found sibling keys!
            pt = obj['player_talent']
            wt = obj['world']
            if isinstance(pt, dict) and isinstance(wt, dict):
                # Check if one is a copy of the other
                if 'name' in pt and 'name' in wt:
                    # They're both player talent refs - use one
                    return pt
                # One might have player_talent inside?
                return pt
        # Search deeper
        for v in obj.values():
            result = find_player_talent(v)
            if result is not None:
                return result
    return None

player_talent = find_player_talent(data)
if not player_talent or 'name' not in str(player_talent):
    player_talent = data.get('player_talent', {})
    if not isinstance(player_talent, dict):
        # Try to find it elsewhere
        pass

wrapper = {'world': actual_data}
if player_talent and isinstance(player_talent, dict):
    wrapper['player_talent'] = player_talent

with open('saves/灰烬列车/world.yaml', 'w', encoding='utf-8', newline='\n') as f:
    yaml.safe_dump(wrapper, f, allow_unicode=True, sort_keys=False)

print("✓ Fixed and saved!")
