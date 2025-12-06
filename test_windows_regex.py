#!/usr/bin/env python3
"""Test Windows backslash regex fix."""
import re

# Test the fixed regex - same as in cli.py
pattern = re.compile(r'@((?:\.\.?[/\\]|[/\\])[^\s@]+)')

# Test cases: (input, should_match, expected_group)
tests = [
    ('@./file.txt', True, './file.txt'),
    ('@../file.txt', True, '../file.txt'),
    ('@/absolute/path.txt', True, '/absolute/path.txt'),
    ('@.\\file.txt', True, '.\\file.txt'),       # Windows relative
    ('@..\\file.txt', True, '..\\file.txt'),     # Windows parent
    ('@\\absolute\\path.txt', True, '\\absolute\\path.txt'),  # Windows absolute
    ('@user@email.com', False, None),            # Email - should NOT match
    ('@simple', False, None),                    # No path chars - should NOT match
]

print('Testing Windows backslash regex fix:')
passed = 0
failed = 0
for test_str, should_match, expected in tests:
    match = pattern.search(test_str)
    if should_match:
        if match:
            actual = match.group(1)
            if actual == expected:
                print(f'  [OK] {repr(test_str)} -> {repr(actual)}')
                passed += 1
            else:
                print(f'  [FAIL] {repr(test_str)} matched {repr(actual)} but expected {repr(expected)}')
                failed += 1
        else:
            print(f'  [FAIL] {repr(test_str)} should match but did not')
            failed += 1
    else:
        if not match:
            print(f'  [OK] {repr(test_str)} correctly did not match')
            passed += 1
        else:
            print(f'  [FAIL] {repr(test_str)} should NOT match but got {repr(match.group(1))}')
            failed += 1

print(f'\nResults: {passed}/{passed+failed} tests passed')
