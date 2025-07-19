import os
import sys

from .initialization.installation_manager import InstallationManager

execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]

__all__ = ["InstallationManager", "execute_dir"]
