def compare(actual: dict, expected: dict):
    results = {}
    for key, expected_val in expected.items():
        actual_val = actual.get(key)
        results[key] = {
            "expected": expected_val,
            "actual": actual_val,
            "status": actual_val == expected_val,
        }
    return results
