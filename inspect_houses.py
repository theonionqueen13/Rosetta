from models_v2 import static_db
for i,h in static_db.houses.items():
    print(i, type(h.keywords), h.keywords)
    if isinstance(h.keywords, dict):
        print('  dict keys:', h.keywords.keys())
    if isinstance(h.keywords, list):
        for item in h.keywords:
            if isinstance(item, dict):
                print('  element dict:', item)
