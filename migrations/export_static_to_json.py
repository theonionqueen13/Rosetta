"""
Export large static data from lookup_v2.py to JSON files for faster loading.
Run this once to generate the JSON files, then the app will use them.
"""
import json
import os

# Import the data from static_data
from src.core.static_data import SABIAN_SYMBOLS, OBJECT_SIGN_COMBO, OBJECT_HOUSE_COMBO

OUTPUT_DIR = os.path.dirname(__file__)

def export_sabian_symbols():
    """
    Export SABIAN_SYMBOLS to JSON.
    Original keys are tuples like ('Aries', 1), convert to "Aries_1" for JSON.
    """
    converted = {}
    for (sign, degree), data in SABIAN_SYMBOLS.items():
        key = f"{sign}_{degree}"
        converted[key] = data
    
    output_path = os.path.join(OUTPUT_DIR, "sabian_symbols.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(converted)} Sabian symbols to {output_path}")
    return len(converted)

def export_object_sign_combo():
    """Export OBJECT_SIGN_COMBO to JSON."""
    output_path = os.path.join(OUTPUT_DIR, "object_sign_combo.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(OBJECT_SIGN_COMBO, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(OBJECT_SIGN_COMBO)} object-sign combos to {output_path}")
    return len(OBJECT_SIGN_COMBO)

def export_object_house_combo():
    """Export OBJECT_HOUSE_COMBO to JSON."""
    output_path = os.path.join(OUTPUT_DIR, "object_house_combo.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(OBJECT_HOUSE_COMBO, f, indent=2, ensure_ascii=False)
    print(f"Exported {len(OBJECT_HOUSE_COMBO)} object-house combos to {output_path}")
    return len(OBJECT_HOUSE_COMBO)

if __name__ == "__main__":
    print("Exporting static data to JSON files...")
    total = 0
    total += export_sabian_symbols()
    total += export_object_sign_combo()
    total += export_object_house_combo()
    print(f"\nDone! Exported {total} total entries.")
    print("\nNext steps:")
    print("1. Update models_v2.py to lazy-load from these JSON files")
    print("2. Remove the large dicts from lookup_v2.py")
