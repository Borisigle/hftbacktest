#!/usr/bin/env python3
"""
Verification script for Python connector setup.
This script tests if the live features are properly built and accessible.
"""

import sys

def test_live_features():
    """Test if live features are available in the built hftbacktest package."""
    try:
        import hftbacktest
        
        # Check if live feature is available
        has_live = hasattr(hftbacktest, 'build_hashmap_livebot')
        print(f"Live feature available: {has_live}")
        
        if has_live:
            # Check if all expected live components are available
            components = [
                'LiveInstrument',
                'build_hashmap_livebot', 
                'build_roivec_livebot',
                'HashMapMarketDepthLiveBot',
                'ROIVectorMarketDepthLiveBot'
            ]
            
            print("Checking live components:")
            for component in components:
                available = hasattr(hftbacktest, component)
                print(f"  {component}: {'✓' if available else '✗'}")
                
            if all(hasattr(hftbacktest, comp) for comp in components):
                print("\n✓ All live features are properly built!")
                return True
            else:
                print("\n✗ Some live features are missing.")
                return False
        else:
            print("✗ Live feature not available. Rebuild with --features live")
            return False
            
    except ImportError as e:
        print(f"✗ Failed to import hftbacktest: {e}")
        return False

def test_basic_instrument_creation():
    """Test basic LiveInstrument creation."""
    try:
        import hftbacktest
        
        if not hasattr(hftbacktest, 'LiveInstrument'):
            print("✗ LiveInstrument not available")
            return False
            
        # Create a basic instrument
        instrument = (
            hftbacktest.LiveInstrument()
            .connector("binancefutures")
            .symbol("BTCUSDT")
            .tick_size(0.1)
            .lot_size(0.001)
        )
        
        print(f"✓ LiveInstrument created successfully:")
        print(f"  Connector: {instrument.connector_name}")
        print(f"  Symbol: {instrument.symbol}")
        print(f"  Tick size: {instrument.tick_size}")
        print(f"  Lot size: {instrument.lot_size}")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to create LiveInstrument: {e}")
        return False

def main():
    """Run all verification tests."""
    print("HftBacktest Python Connector Verification")
    print("=" * 50)
    
    tests = [
        ("Live Features Test", test_live_features),
        ("Instrument Creation Test", test_basic_instrument_creation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * len(test_name))
        result = test_func()
        results.append(result)
        
    print("\n" + "=" * 50)
    print("Summary:")
    
    if all(results):
        print("✓ All tests passed! Python connector is properly set up.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the build process.")
        sys.exit(1)

if __name__ == "__main__":
    main()