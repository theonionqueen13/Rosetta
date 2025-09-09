#!/bin/bash
# Pre-commit check script
# Run this before submitting a PR to catch issues early

set -e

echo "🔍 Running pre-commit checks..."
echo ""

echo "1️⃣ Checking dependencies..."
python -c "
import subprocess
import sys
try:
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--dry-run'], 
                          capture_output=True, text=True, check=False)
    if result.returncode == 0:
        print('✅ All dependencies resolve correctly')
    else:
        print('❌ Dependency resolution failed:')
        print(result.stderr)
        sys.exit(1)
except Exception as e:
    print(f'❌ Error checking dependencies: {e}')
    sys.exit(1)
"
echo ""

echo "2️⃣ Checking Python syntax..."
flake8 . --count --select=E9,F63,F7,F82 --ignore=F824 --show-source --statistics --exclude=.venv,__pycache__,backups
echo "✅ No syntax errors found"
echo ""

echo "3️⃣ Running test suite..."
pytest tests/ -v --tb=short
echo "✅ All tests pass"
echo ""

echo "4️⃣ Testing core module imports..."
python -c "
from rosetta.calc import calculate_chart
from rosetta.patterns import detect_shapes  
from rosetta.drawing import draw_aspect_lines
from rosetta.lookup import ASPECTS
from rosetta.helpers import deg_to_rad
print('✅ All core modules import successfully')
"
echo ""

echo "5️⃣ Testing basic chart calculation..."
python -c "
from rosetta.calc import calculate_chart
chart = calculate_chart(1990, 7, 29, 1, 39, None, 38.0469166, -97.3447244, tz_name='America/Chicago')
assert len(chart) > 20, 'Chart should have at least 20 objects'
print(f'✅ Chart calculation successful: {len(chart)} objects')
"
echo ""

echo "6️⃣ Checking code formatting (optional)..."
if command -v black &> /dev/null; then
    if black --check --diff . 2>/dev/null; then
        echo "✅ Code formatting is good"
    else
        echo "ℹ️ Code formatting suggestions available (run 'black .' to apply)"
    fi
else
    echo "ℹ️ Black not installed, skipping formatting check"
fi
echo ""

echo "🎉 All pre-commit checks passed!"
echo "Your code is ready for PR submission."
