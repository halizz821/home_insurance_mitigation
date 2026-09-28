"""Tools package for Sentinel System."""

__path__ = __import__('pkgutil').extend_path(__path__, __name__)

from .mcp_client import EnvironmentCanadaMCPClient

__all__ = ["EnvironmentCanadaMCPClient"]
