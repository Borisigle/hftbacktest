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
    from .connector_runner import (
        ConnectorRunner,
        ConnectorConfig,
        ConnectorRunnerError,
        ConnectorBuildError,
        ConnectorStartupError,
        ConnectorNotFoundError
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
        'StubConnectorBot',
        'ConnectorRunner',
        'ConnectorConfig',
        'ConnectorRunnerError',
        'ConnectorBuildError',
        'ConnectorStartupError',
        'ConnectorNotFoundError',
    ]
    
except ImportError as e:
    import warnings
    warnings.warn(
        f"Live features not available. Build with 'live' feature to enable: "
        f"maturin develop --features live. Error: {e}",
        ImportWarning
    )
    
    # Still try to import stub and connector_runner since they don't require live feature
    try:
        from .stub import StubConnectorBot
        from .connector_runner import (
            ConnectorRunner,
            ConnectorConfig,
            ConnectorRunnerError,
            ConnectorBuildError,
            ConnectorStartupError,
            ConnectorNotFoundError
        )
        __all__ = [
            'StubConnectorBot',
            'ConnectorRunner',
            'ConnectorConfig',
            'ConnectorRunnerError',
            'ConnectorBuildError',
            'ConnectorStartupError',
            'ConnectorNotFoundError',
        ]
    except ImportError:
        __all__ = []
