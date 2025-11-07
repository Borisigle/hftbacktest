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
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(
        f"Live features not available. Build with 'live' feature to enable: "
        f"maturin develop --features live. Error: {e}",
        ImportWarning
    )
    
    __all__ = []
