"""
Connector runner for managing the lifecycle of the connector binary.

This module provides a utility to build, start, stop, and manage the Rust connector
binary that streams market data via Iceoryx2 IPC. It handles:
- Building the connector binary if missing
- Spawning the process with configuration
- Health checks to ensure Iceoryx channels are available
- Graceful shutdown with proper signal handling
- Log capture and error reporting
"""

import os
import sys
import time
import subprocess
import signal
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConnectorConfig:
    """Configuration for the connector runner."""
    
    connector_name: str
    """Unique name for this connector instance (used for Iceoryx channels)"""
    
    connector_type: str
    """Type of connector: 'binancefutures', 'binancespot', or 'bybit'"""
    
    config_path: Path
    """Path to the TOML configuration file"""
    
    project_root: Optional[Path] = None
    """Root directory of the project (defaults to auto-detected)"""
    
    binary_path: Optional[Path] = None
    """Path to connector binary (defaults to target/release/connector)"""
    
    build_features: Optional[List[str]] = None
    """Cargo features to enable when building (defaults to [connector_type])"""
    
    startup_timeout: float = 10.0
    """Maximum time in seconds to wait for connector startup"""
    
    shutdown_timeout: float = 5.0
    """Maximum time in seconds to wait for graceful shutdown"""
    
    env: Dict[str, str] = field(default_factory=dict)
    """Additional environment variables for the connector process"""
    
    auto_build: bool = True
    """Whether to automatically build the connector if binary is missing"""
    
    capture_output: bool = True
    """Whether to capture and log connector stdout/stderr"""


class ConnectorRunnerError(Exception):
    """Base exception for connector runner errors."""
    pass


class ConnectorBuildError(ConnectorRunnerError):
    """Raised when building the connector fails."""
    pass


class ConnectorStartupError(ConnectorRunnerError):
    """Raised when the connector fails to start."""
    pass


class ConnectorNotFoundError(ConnectorRunnerError):
    """Raised when the connector binary is not found."""
    pass


class ConnectorRunner:
    """
    Manages the lifecycle of the connector binary.
    
    Example:
        >>> config = ConnectorConfig(
        ...     connector_name="binancefutures",
        ...     connector_type="binancefutures",
        ...     config_path=Path("config.toml")
        ... )
        >>> runner = ConnectorRunner(config)
        >>> runner.build_if_missing()
        >>> runner.start()
        >>> try:
        ...     # Your trading logic here
        ...     pass
        ... finally:
        ...     runner.stop()
    
    Or use as a context manager:
        >>> with ConnectorRunner(config) as runner:
        ...     # Your trading logic here
        ...     pass
    """
    
    def __init__(self, config: ConnectorConfig):
        """
        Initialize the connector runner.
        
        Args:
            config: Configuration for the connector
        """
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._setup_paths()
        self._validate_config()
    
    def _setup_paths(self):
        """Setup and validate file paths."""
        if self.config.project_root is None:
            self.config.project_root = self._find_project_root()
        
        if self.config.binary_path is None:
            self.config.binary_path = (
                self.config.project_root / "target" / "release" / "connector"
            )
        
        if not self.config.config_path.is_absolute():
            self.config.config_path = self.config.config_path.resolve()
    
    def _find_project_root(self) -> Path:
        """
        Find the project root by looking for workspace Cargo.toml.
        
        Returns:
            Path to the project root
            
        Raises:
            ConnectorRunnerError: If project root cannot be found
        """
        # Start from current file and search upwards
        current = Path(__file__).resolve().parent
        
        for _ in range(10):  # Limit search depth
            cargo_toml = current / "Cargo.toml"
            if cargo_toml.exists():
                # Check if it's a workspace
                try:
                    with open(cargo_toml) as f:
                        content = f.read()
                        if "[workspace]" in content:
                            return current
                        # Also check for connector/Cargo.toml
                        if (current / "connector" / "Cargo.toml").exists():
                            return current
                except IOError:
                    pass
            
            parent = current.parent
            if parent == current:
                break
            current = parent
        
        # Fallback: try to find from environment or common locations
        if "HFTBACKTEST_ROOT" in os.environ:
            root = Path(os.environ["HFTBACKTEST_ROOT"])
            if root.exists():
                return root
        
        raise ConnectorRunnerError(
            "Could not find project root. Set HFTBACKTEST_ROOT environment variable "
            "or ensure you're running from within the project directory."
        )
    
    def _validate_config(self):
        """Validate the configuration."""
        if not self.config.config_path.exists():
            raise ConnectorRunnerError(
                f"Configuration file not found: {self.config.config_path}"
            )
        
        valid_types = ["binancefutures", "binancespot", "bybit"]
        if self.config.connector_type not in valid_types:
            raise ConnectorRunnerError(
                f"Invalid connector type '{self.config.connector_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )
    
    def binary_exists(self) -> bool:
        """Check if the connector binary exists."""
        return self.config.binary_path.exists()
    
    def build(self, force: bool = False):
        """
        Build the connector binary.
        
        Args:
            force: If True, rebuild even if binary already exists
            
        Raises:
            ConnectorBuildError: If build fails
        """
        if not force and self.binary_exists():
            logger.info(f"Connector binary already exists at {self.config.binary_path}")
            return
        
        features = self.config.build_features or [self.config.connector_type]
        features_str = ",".join(features)
        
        manifest_path = self.config.project_root / "connector" / "Cargo.toml"
        
        logger.info(f"Building connector with features: {features_str}")
        
        cmd = [
            "cargo", "build",
            "--release",
            "--manifest-path", str(manifest_path),
            "--features", features_str
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.config.project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for build
            )
            
            if result.returncode != 0:
                raise ConnectorBuildError(
                    f"Build failed with exit code {result.returncode}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
            
            if not self.binary_exists():
                raise ConnectorBuildError(
                    f"Build completed but binary not found at {self.config.binary_path}"
                )
            
            logger.info(f"Successfully built connector at {self.config.binary_path}")
            
        except subprocess.TimeoutExpired:
            raise ConnectorBuildError("Build timed out after 5 minutes")
        except FileNotFoundError:
            raise ConnectorBuildError(
                "cargo command not found. Ensure Rust toolchain is installed."
            )
    
    def build_if_missing(self):
        """Build the connector binary if it doesn't exist."""
        if not self.binary_exists():
            if self.config.auto_build:
                logger.info("Connector binary not found, building...")
                self.build()
            else:
                raise ConnectorNotFoundError(
                    f"Connector binary not found at {self.config.binary_path}. "
                    "Set auto_build=True to build automatically."
                )
    
    def start(self):
        """
        Start the connector process.
        
        Raises:
            ConnectorStartupError: If the connector fails to start
            ConnectorNotFoundError: If the binary doesn't exist
        """
        if self.process is not None:
            raise ConnectorRunnerError("Connector is already running")
        
        if not self.binary_exists():
            raise ConnectorNotFoundError(
                f"Connector binary not found at {self.config.binary_path}. "
                "Call build_if_missing() first."
            )
        
        cmd = [
            str(self.config.binary_path),
            self.config.connector_name,
            self.config.connector_type,
            str(self.config.config_path)
        ]
        
        env = os.environ.copy()
        env.update(self.config.env)
        
        logger.info(f"Starting connector: {' '.join(cmd)}")
        
        try:
            if self.config.capture_output:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    cwd=str(self.config.project_root)
                )
            else:
                self.process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=str(self.config.project_root)
                )
            
            # Give the process a moment to start
            time.sleep(0.5)
            
            # Check if process died immediately
            if self.process.poll() is not None:
                stdout, stderr = "", ""
                if self.config.capture_output:
                    stdout, stderr = self.process.communicate()
                
                raise ConnectorStartupError(
                    f"Connector process died immediately with exit code {self.process.returncode}\n"
                    f"stdout: {stdout}\n"
                    f"stderr: {stderr}"
                )
            
            logger.info(f"Connector started with PID {self.process.pid}")
            
        except FileNotFoundError:
            raise ConnectorNotFoundError(
                f"Connector binary not found at {self.config.binary_path}"
            )
        except Exception as e:
            raise ConnectorStartupError(f"Failed to start connector: {e}")
    
    def wait_for_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the connector to be ready by checking Iceoryx channels.
        
        Args:
            timeout: Maximum time to wait in seconds (uses config.startup_timeout if None)
            
        Returns:
            True if connector is ready, False if timeout
            
        Raises:
            ConnectorStartupError: If the connector process dies while waiting
        """
        if self.process is None:
            raise ConnectorRunnerError("Connector is not running")
        
        timeout = timeout or self.config.startup_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for connector to be ready (timeout: {timeout}s)...")
        
        # Try to import the live module to check channel availability
        try:
            import hftbacktest
            from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
        except ImportError as e:
            logger.warning(
                f"Cannot verify Iceoryx channel availability: {e}. "
                "Assuming connector is ready based on process status only."
            )
            # Just wait a bit and check process is still alive
            time.sleep(2)
            if self.process.poll() is not None:
                raise ConnectorStartupError(
                    f"Connector process died with exit code {self.process.returncode}"
                )
            return True
        
        # Try to create a minimal bot to verify channel availability
        while time.time() - start_time < timeout:
            # Check if process is still alive
            if self.process.poll() is not None:
                stdout, stderr = "", ""
                if self.config.capture_output:
                    stdout, stderr = self.process.communicate()
                
                raise ConnectorStartupError(
                    f"Connector process died with exit code {self.process.returncode}\n"
                    f"stdout: {stdout}\n"
                    f"stderr: {stderr}"
                )
            
            # Try to connect
            try:
                instrument = (
                    LiveInstrument()
                    .connector(self.config.connector_name)
                    .symbol("_HEALTH_CHECK_")
                    .tick_size(0.01)
                    .lot_size(0.001)
                )
                bot = HashMapMarketDepthLiveBot([instrument])
                # If we got here, channels are available
                logger.info("Connector is ready (Iceoryx channels available)")
                return True
            except Exception as e:
                logger.debug(f"Channel not ready yet: {e}")
                time.sleep(0.5)
        
        logger.warning(f"Connector did not become ready within {timeout}s")
        return False
    
    def is_running(self) -> bool:
        """Check if the connector process is running."""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def stop(self, timeout: Optional[float] = None):
        """
        Stop the connector process gracefully.
        
        Args:
            timeout: Maximum time to wait for shutdown (uses config.shutdown_timeout if None)
        """
        if self.process is None:
            logger.debug("Connector is not running")
            return
        
        if not self.is_running():
            logger.debug("Connector process already stopped")
            self.process = None
            return
        
        timeout = timeout or self.config.shutdown_timeout
        
        logger.info(f"Stopping connector (PID {self.process.pid})...")
        
        try:
            # Try graceful shutdown with SIGTERM
            self.process.terminate()
            
            try:
                self.process.wait(timeout=timeout)
                logger.info("Connector stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"Connector did not stop within {timeout}s, forcing kill..."
                )
                self.process.kill()
                self.process.wait(timeout=5)
                logger.info("Connector killed")
            
        except Exception as e:
            logger.error(f"Error stopping connector: {e}")
        finally:
            self.process = None
    
    def get_output(self) -> tuple[str, str]:
        """
        Get captured stdout and stderr from the connector process.
        
        Returns:
            Tuple of (stdout, stderr) strings
            
        Raises:
            ConnectorRunnerError: If output capture is not enabled or process not started
        """
        if not self.config.capture_output:
            raise ConnectorRunnerError("Output capture is not enabled")
        
        if self.process is None:
            raise ConnectorRunnerError("Connector process has not been started")
        
        if self.is_running():
            raise ConnectorRunnerError(
                "Cannot get output while process is running. Call stop() first."
            )
        
        stdout, stderr = self.process.communicate()
        return stdout or "", stderr or ""
    
    def __enter__(self):
        """Context manager entry."""
        self.build_if_missing()
        self.start()
        self.wait_for_ready()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
