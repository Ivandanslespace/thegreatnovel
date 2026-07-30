import yaml

with open('saves/灰烬列车/world.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

l = data
print("level 0:", list(l.keys())[:3])
for i in range(1, 10):
    if not isinstance(l, dict):
        print(f"level {i}: Not a dict")
        break
    keys = list(l.keys())
    print(f"level {i}: {keys[:3]}")
    if len(keys) == 1:
        l = l[keys[0]]
    else:
        # Multiple keys - check if 'world' is one of them
        if 'world' in l:
            print(f"Found 'world' key at level {i}, using it")
            l = l['world']
            continue
        else:
            print(f"Unexpected multi-key dict at level {i}")
            break
    name = l.get('name') if isinstance(l, dict) else None
    print(f"  -> name: {name}")
