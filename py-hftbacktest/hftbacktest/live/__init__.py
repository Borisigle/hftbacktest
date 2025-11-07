try:
    from .client import LiveClient, LiveClientError
    from .models import (
        Trade,
        BookLevel,
        BookUpdate,
        DepthSnapshot,
        OrderRequest,
        OrderResponse,
        ConnectionHealth,
        EventType,
        Side
    )
    from .stub import StubConnectorBot
    
    __all__ = [
        'LiveClient',
        'LiveClientError',
        'Trade',
        'BookLevel',
        'BookUpdate',
        'DepthSnapshot',
        'OrderRequest',
        'OrderResponse',
        'ConnectionHealth',
        'EventType',
        'Side',
        'StubConnectorBot',
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(
        f"Live features not available. Build with 'live' feature to enable: "
        f"maturin develop --features live. Error: {e}",
        ImportWarning
    )
    
    # Still try to import stub since it doesn't require live feature
    try:
        from .stub import StubConnectorBot
        __all__ = ['StubConnectorBot']
    except ImportError:
        __all__ = []
