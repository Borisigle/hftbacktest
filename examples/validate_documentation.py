#!/usr/bin/env python3
"""
Documentation validation script.
Checks that the documented PyO3 bindings actually exist in the source code.
"""

import os
import re
from pathlib import Path

def check_pyo3_bindings():
    """Check that documented PyO3 bindings exist in the source."""
    pyo3_file = Path("/home/engine/project/py-hftbacktest/src/lib.rs")
    
    if not pyo3_file.exists():
        print("✗ PyO3 source file not found")
        return False
    
    content = pyo3_file.read_text()
    
    # Check for documented bindings
    expected_bindings = [
        "LiveInstrument",
        "build_hashmap_livebot", 
        "build_roivec_livebot",
        "HashMapMarketDepthLiveBot",
        "ROIVectorMarketDepthLiveBot"
    ]
    
    print("Checking PyO3 bindings in source:")
    all_found = True
    
    for binding in expected_bindings:
        # Check if binding exists and is conditionally compiled with 'live' feature
        found = binding in content
        conditional = f'#[cfg(feature = "live")]' in content and binding in content
        
        status = "✓" if (found and conditional) else "✗"
        print(f"  {binding}: {status}")
        
        if not (found and conditional):
            all_found = False
            if not found:
                print(f"    Not found in source")
            if not conditional:
                print(f"    Not conditionally compiled with 'live' feature")
    
    return all_found

def check_connector_examples():
    """Check that connector configuration examples exist."""
    examples_dir = Path("/home/engine/project/connector/examples")
    
    expected_configs = [
        "binancefutures.toml",
        "binancespot.toml", 
        "bybit.toml"
    ]
    
    print("\nChecking connector configuration examples:")
    all_found = True
    
    for config in expected_configs:
        config_path = examples_dir / config
        found = config_path.exists()
        status = "✓" if found else "✗"
        print(f"  {config}: {status}")
        
        if not found:
            all_found = False
    
    return all_found

def check_main_rs_structure():
    """Check that main.rs has the expected CLI structure."""
    main_file = Path("/home/engine/project/connector/src/main.rs")
    
    if not main_file.exists():
        print("✗ connector main.rs not found")
        return False
    
    content = main_file.read_text()
    
    print("\nChecking connector CLI structure:")
    
    # Check for Args struct
    has_args = "struct Args" in content and "Parser" in content
    print(f"  CLI Args struct: {'✓' if has_args else '✗'}")
    
    # Check for main function
    has_main = "fn main()" in content
    print(f"  Main function: {'✓' if has_main else '✗'}")
    
    # Check for connector matching
    has_matching = '"binancefutures"' in content and '"bybit"' in content
    print(f"  Connector types: {'✓' if has_matching else '✗'}")
    
    return has_args and has_main and has_matching

def check_documentation_links():
    """Check that documentation references are correct."""
    doc_file = Path("/home/engine/project/docs/python_connector_setup.md")
    
    if not doc_file.exists():
        print("✗ Documentation file not found")
        return False
    
    content = doc_file.read_text()
    
    print("\nChecking documentation references:")
    
    # Check for key sections
    sections = [
        "Prerequisites",
        "Building the Components", 
        "Configuration",
        "Running the System",
        "Troubleshooting"
    ]
    
    all_found = True
    for section in sections:
        found = section in content
        status = "✓" if found else "✗"
        print(f"  {section} section: {status}")
        
        if not found:
            all_found = False
    
    return all_found

def main():
    """Run all validation checks."""
    print("HftBacktest Documentation Validation")
    print("=" * 50)
    
    checks = [
        ("PyO3 Bindings", check_pyo3_bindings),
        ("Connector Examples", check_connector_examples),
        ("Main.rs Structure", check_main_rs_structure),
        ("Documentation Content", check_documentation_links),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n{check_name}:")
        print("-" * len(check_name))
        result = check_func()
        results.append((check_name, result))
        
    print("\n" + "=" * 50)
    print("Validation Summary:")
    
    all_passed = all(result for _, result in results)
    
    for check_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {check_name}: {status}")
    
    if all_passed:
        print("\n🎉 All documentation validation checks passed!")
        return True
    else:
        print("\n❌ Some validation checks failed.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)