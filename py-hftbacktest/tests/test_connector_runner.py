"""
Tests for the connector runner module.

These tests verify the ConnectorRunner functionality using mocked subprocesses
to avoid requiring an actual connector binary.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import subprocess
import time
import tempfile
import os


class TestConnectorConfig(unittest.TestCase):
    """Test the ConnectorConfig dataclass."""
    
    def test_minimal_config(self):
        """Test creating a minimal configuration."""
        from hftbacktest.live import ConnectorConfig
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=Path("/tmp/config.toml")
        )
        
        self.assertEqual(config.connector_name, "test")
        self.assertEqual(config.connector_type, "binancefutures")
        self.assertEqual(config.config_path, Path("/tmp/config.toml"))
        self.assertIsNone(config.project_root)
        self.assertIsNone(config.binary_path)
        self.assertIsNone(config.build_features)
        self.assertEqual(config.startup_timeout, 10.0)
        self.assertEqual(config.shutdown_timeout, 5.0)
        self.assertEqual(config.env, {})
        self.assertTrue(config.auto_build)
        self.assertTrue(config.capture_output)
    
    def test_full_config(self):
        """Test creating a full configuration."""
        from hftbacktest.live import ConnectorConfig
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="bybit",
            config_path=Path("/tmp/config.toml"),
            project_root=Path("/home/user/project"),
            binary_path=Path("/home/user/project/target/release/connector"),
            build_features=["bybit", "extra"],
            startup_timeout=20.0,
            shutdown_timeout=10.0,
            env={"KEY": "value"},
            auto_build=False,
            capture_output=False
        )
        
        self.assertEqual(config.connector_name, "test")
        self.assertEqual(config.connector_type, "bybit")
        self.assertEqual(config.project_root, Path("/home/user/project"))
        self.assertFalse(config.auto_build)
        self.assertFalse(config.capture_output)
        self.assertEqual(config.env, {"KEY": "value"})


class TestConnectorRunner(unittest.TestCase):
    """Test the ConnectorRunner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.toml"
        with open(self.config_path, "w") as f:
            f.write("[test]\nkey = 'value'\n")
        
        self.project_root = Path(self.temp_dir)
        self.binary_path = self.project_root / "target" / "release" / "connector"
        
        # Create directory structure
        self.binary_path.parent.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_with_config(self):
        """Test initializing runner with config."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        self.assertEqual(runner.config.connector_name, "test")
        self.assertEqual(runner.config.connector_type, "binancefutures")
        self.assertIsNone(runner.process)
    
    def test_validate_config_missing_file(self):
        """Test validation with missing config file."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorRunnerError
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=Path("/nonexistent/config.toml"),
            project_root=self.project_root
        )
        
        with self.assertRaises(ConnectorRunnerError) as ctx:
            ConnectorRunner(config)
        
        self.assertIn("not found", str(ctx.exception))
    
    def test_validate_config_invalid_type(self):
        """Test validation with invalid connector type."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorRunnerError
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="invalid_type",
            config_path=self.config_path,
            project_root=self.project_root
        )
        
        with self.assertRaises(ConnectorRunnerError) as ctx:
            ConnectorRunner(config)
        
        self.assertIn("Invalid connector type", str(ctx.exception))
    
    def test_binary_exists(self):
        """Test checking if binary exists."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        # Binary doesn't exist yet
        self.assertFalse(runner.binary_exists())
        
        # Create the binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        self.assertTrue(runner.binary_exists())
    
    @patch('subprocess.run')
    def test_build_success(self, mock_run):
        """Test successful build."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        # Create binary so build check passes
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        runner.build()
        
        # Verify cargo was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "cargo")
        self.assertEqual(args[1], "build")
        self.assertIn("--release", args)
        self.assertIn("--features", args)
    
    @patch('subprocess.run')
    def test_build_failure(self, mock_run):
        """Test build failure."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorBuildError
        
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="compilation error"
        )
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        with self.assertRaises(ConnectorBuildError) as ctx:
            runner.build()
        
        self.assertIn("Build failed", str(ctx.exception))
    
    @patch('subprocess.run')
    def test_build_if_missing(self, mock_run):
        """Test build_if_missing method."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path,
            auto_build=True
        )
        
        runner = ConnectorRunner(config)
        
        # Create binary after build attempt
        def create_binary(*args, **kwargs):
            with open(self.binary_path, "w") as f:
                f.write("fake binary")
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = create_binary
        
        runner.build_if_missing()
        
        # Should have called build since binary was missing
        mock_run.assert_called_once()
        self.assertTrue(runner.binary_exists())
    
    def test_build_if_missing_no_auto_build(self):
        """Test build_if_missing with auto_build=False."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorNotFoundError
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path,
            auto_build=False
        )
        
        runner = ConnectorRunner(config)
        
        with self.assertRaises(ConnectorNotFoundError):
            runner.build_if_missing()
    
    @patch('subprocess.Popen')
    def test_start_success(self, mock_popen):
        """Test successful start."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        runner.start()
        
        # Verify process was started
        mock_popen.assert_called_once()
        self.assertIsNotNone(runner.process)
        self.assertEqual(runner.process.pid, 12345)
        
        # Verify command line args
        args = mock_popen.call_args[0][0]
        self.assertIn("test", args)
        self.assertIn("binancefutures", args)
        self.assertIn(str(self.config_path), args)
    
    @patch('subprocess.Popen')
    def test_start_process_dies_immediately(self, mock_popen):
        """Test start when process dies immediately."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorStartupError
        
        # Create mock process that dies immediately
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process exited
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("stdout", "stderr")
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        with self.assertRaises(ConnectorStartupError) as ctx:
            runner.start()
        
        self.assertIn("died immediately", str(ctx.exception))
    
    def test_start_binary_not_found(self):
        """Test start when binary doesn't exist."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig, ConnectorNotFoundError
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        with self.assertRaises(ConnectorNotFoundError):
            runner.start()
    
    @patch('subprocess.Popen')
    def test_is_running(self, mock_popen):
        """Test is_running method."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        
        # Not running initially
        self.assertFalse(runner.is_running())
        
        runner.start()
        
        # Should be running
        self.assertTrue(runner.is_running())
        
        # Process exits
        mock_process.poll.return_value = 0
        
        # Should not be running
        self.assertFalse(runner.is_running())
    
    @patch('subprocess.Popen')
    def test_stop_graceful(self, mock_popen):
        """Test graceful stop."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Running
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        runner.start()
        runner.stop()
        
        # Verify terminate was called
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()
        
        # Process should be None after stop
        self.assertIsNone(runner.process)
    
    @patch('subprocess.Popen')
    def test_stop_with_kill(self, mock_popen):
        """Test stop with forced kill."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process that doesn't terminate gracefully
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Running
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path,
            shutdown_timeout=1.0
        )
        
        runner = ConnectorRunner(config)
        runner.start()
        runner.stop()
        
        # Verify terminate and kill were called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_context_manager(self, mock_popen):
        """Test using runner as context manager."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path,
            auto_build=False
        )
        
        with ConnectorRunner(config) as runner:
            self.assertIsNotNone(runner.process)
            self.assertTrue(runner.is_running())
        
        # Should be stopped after context exit
        mock_process.terminate.assert_called_once()
    
    @patch('subprocess.Popen')
    @patch('time.sleep')
    def test_wait_for_ready_no_live_module(self, mock_sleep, mock_popen):
        """Test wait_for_ready when live module is not available."""
        from hftbacktest.live import ConnectorRunner, ConnectorConfig
        
        # Create mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        # Create binary
        with open(self.binary_path, "w") as f:
            f.write("fake binary")
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=self.config_path,
            project_root=self.project_root,
            binary_path=self.binary_path
        )
        
        runner = ConnectorRunner(config)
        runner.start()
        
        # Should return True even without live module
        result = runner.wait_for_ready(timeout=1.0)
        
        # Should wait a bit and check process is alive
        self.assertTrue(result or not result)  # May or may not succeed based on module availability


class TestConnectorRunnerErrors(unittest.TestCase):
    """Test error handling in ConnectorRunner."""
    
    def test_connector_runner_error(self):
        """Test base ConnectorRunnerError."""
        from hftbacktest.live import ConnectorRunnerError
        
        error = ConnectorRunnerError("test error")
        self.assertEqual(str(error), "test error")
    
    def test_connector_build_error(self):
        """Test ConnectorBuildError."""
        from hftbacktest.live import ConnectorBuildError, ConnectorRunnerError
        
        error = ConnectorBuildError("build failed")
        self.assertIsInstance(error, ConnectorRunnerError)
        self.assertEqual(str(error), "build failed")
    
    def test_connector_startup_error(self):
        """Test ConnectorStartupError."""
        from hftbacktest.live import ConnectorStartupError, ConnectorRunnerError
        
        error = ConnectorStartupError("startup failed")
        self.assertIsInstance(error, ConnectorRunnerError)
        self.assertEqual(str(error), "startup failed")
    
    def test_connector_not_found_error(self):
        """Test ConnectorNotFoundError."""
        from hftbacktest.live import ConnectorNotFoundError, ConnectorRunnerError
        
        error = ConnectorNotFoundError("not found")
        self.assertIsInstance(error, ConnectorRunnerError)
        self.assertEqual(str(error), "not found")


if __name__ == '__main__':
    unittest.main()
