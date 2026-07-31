import yaml

with open('saves/灰烬列车/world.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Navigate to level 7 (the actual world content)
l = data
for i in range(7):
    if isinstance(l, dict) and 'world' in l:
        l = l['world']
    else:
        print(f"Failed at level {i}")
        break

actual_world = l if isinstance(l, dict) else {}
print("name:", actual_world.get('name'))

# Now we need to construct proper wrapper
# The original player_talent is available somewhere in the tree
# Let's search recursively for a dict that contains BOTH 'world' AND 'player_talent'
def find_siblings(obj, target_keys):
    if not isinstance(obj, dict):
        return None
    keys = set(obj.keys())
    if target_keys.issubset(keys):
        return obj
    # Search deeper
    for v in obj.values():
        result = find_siblings(v, target_keys)
        if result is not None:
            return result
    return None

siblings_dict = find_siblings(data, {'world', 'player_talent'})
if siblings_dict and 'player_talent' in siblings_dict:
    actual_player_talent = siblings_dict['player_talent']
    print("Found player_talent")
elif isinstance(data.get('player_talent'), dict):
    actual_player_talent = data['player_talent']
else:
    actual_player_talent = {}

wrapper = {'world': actual_world}
if actual_player_talent:
    wrapper['player_talent'] = actual_player_talent

with open('saves/灰烬列车/world.yaml', 'w', encoding='utf-8', newline='\n') as f:
    yaml.safe_dump(wrapper, f, allow_unicode=True, sort_keys=False)

print("✓ Fixed!")
