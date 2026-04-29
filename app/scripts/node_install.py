import asyncio
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import distro
import httpx

from ..utils.logger import logger
from ..utils.utils import get_startup_info

current_platform = platform.system()
execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]
node_path = os.path.join(execute_dir, "node")
startupinfo = get_startup_info()


async def unzip_file(zip_path: str | Path, extract_to: str | Path, delete: bool = True) -> None:
    if not os.path.exists(extract_to):
        os.makedirs(extract_to, exist_ok=True)

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _sync_unzip, zip_path, extract_to)
        logger.debug(f"Compressed file decompression completed: {zip_path}")
    except Exception as e:
        logger.error(f"Failed to decompress the compressed file: {e}")
        raise Exception("Failed to decompress the compressed file")

    if delete and os.path.exists(zip_path):
        os.remove(zip_path)


def _sync_unzip(zip_path: str | Path, extract_to: str | Path) -> None:
    if not zipfile.is_zipfile(zip_path):
        os.remove(zip_path)
        logger.error(f"The file is not a valid ZIP file: {zip_path}")
        raise ValueError("The file is not a valid ZIP file")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)


async def install_nodejs_windows(update_progress):
    try:
        logger.warning("Node.js is not installed.")
        logger.debug("Installing the stable version of Node.js for Windows...")
        await update_progress(0.1, "Get Node.js installation resources")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get("https://nodejs.cn/download/")
            if response.status_code == 200:
                text = response.text
                match = re.search("https://npmmirror.com/mirrors/node/(v.*?)/node-(v.*?)-x64.msi", text)
                if match:
                    version = match.group(1)
                    system_bit = "x64" if "32" not in platform.machine() else "x86"
                    url = f"https://npmmirror.com/mirrors/node/{version}/node-{version}-win-{system_bit}.zip"
                else:
                    logger.error("Failed to retrieve the download URL for the latest version of Node.js")
                    raise Exception("The resource address cannot be accessed")

                full_file_name = url.rsplit("/", maxsplit=1)[-1]
                zip_file_path = Path(execute_dir) / full_file_name

                if Path(zip_file_path).exists():
                    await update_progress(0.8, "Node.js installation file already exists")
                else:
                    await update_progress(0.2, "Start downloading Node.js installation package")
                    async with client.stream("GET", url) as resp:
                        if resp.status_code != 200:
                            raise Exception("The resource address cannot be accessed")

                        total_size = int(resp.headers.get("Content-Length", 0))
                        downloaded = 0
                        with open(zip_file_path, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                f.write(chunk)
                                downloaded += len(chunk)

                                progress = 0.2 + 0.6 * (downloaded / total_size)
                                await update_progress(
                                    round(progress, 2), f"Downloading... {downloaded // 1024}KB/{total_size // 1024}KB"
                                )

                await update_progress(0.8, "Extracting and cleaning installation files")
                await unzip_file(zip_file_path, execute_dir)
                extract_dir_path = str(zip_file_path).rsplit(".", maxsplit=1)[0]
                new_extract_dir_path = Path(extract_dir_path).parent / "node"
                await update_progress(0.9, "Configuring Node.js environment variables")
                if Path(extract_dir_path).exists():
                    if Path(new_extract_dir_path).exists():
                        shutil.rmtree(new_extract_dir_path)
                    os.rename(extract_dir_path, new_extract_dir_path)
                    os.environ["PATH"] = execute_dir + "/node" + os.pathsep + os.environ.get("PATH")
                    result = subprocess.run(["node", "-v"], capture_output=True, startupinfo=startupinfo)
                    if result.returncode == 0:
                        return True
                    else:
                        raise Exception("Please restart the program")
            else:
                logger.error("Failed to retrieve the Node.js version page")
                raise Exception("Failed to obtain the Node.js download address")

    except Exception as e:
        logger.error(f"Node.js installation failed, {e}")
        raise RuntimeError(f"Node.js install failed, {e}") from None


async def install_nodejs_centos(update_progress):
    try:
        logger.warning("Node.js is not installed.")
        logger.debug("Installing the latest version of Node.js for CentOS...")
        await update_progress(0.1, "Get Node.js installation resources")
        result = subprocess.run(
            "curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/nodesource/rpm/setup_lts.x | bash -",
            shell=True,
            capture_output=True,
            startupinfo=startupinfo,
        )
        if result.returncode != 0:
            logger.error("Failed to run NodeSource installation script")

        result = subprocess.run(["yum", "install", "-y", "epel-release"], capture_output=True, startupinfo=startupinfo)
        if result.returncode != 0:
            logger.error("Failed to install EPEL repository")

        result = subprocess.run(["yum", "install", "-y", "nodejs"], capture_output=True, startupinfo=startupinfo)
        if result.returncode == 0:
            logger.debug("Node.js installation was successful. Restart for changes to take effect.")
            return True
        else:
            logger.error("Node.js installation failed")
            raise Exception("Please manually install by yourself")
    except Exception as e:
        logger.error(f"Node.js installation failed {e}")
        raise RuntimeError(f"Node.js install failed, {e}") from None


async def install_nodejs_ubuntu(update_progress):
    try:
        logger.warning("Node.js is not installed.")
        logger.debug("Installing the latest version of Node.js for Ubuntu...")
        await update_progress(0.1, "Get Node.js installation resources")
        install_script = "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -"
        result = subprocess.run(install_script, shell=True, capture_output=True, startupinfo=startupinfo)
        if result.returncode != 0:
            logger.error("Failed to run NodeSource installation script")

        install_command = ["apt", "install", "-y", "nodejs"]
        result = subprocess.run(install_command, capture_output=True, startupinfo=startupinfo)
        if result.returncode == 0:
            logger.debug("Node.js installation was successful. Restart for changes to take effect.")
            return True
        else:
            logger.error("Node.js installation failed")
            raise Exception("Please manually install by yourself")
    except Exception as e:
        logger.error(f"Node.js installation failed, {e}")
        raise RuntimeError(f"Node.js install failed, {e}") from None


async def install_nodejs_mac(update_progress):
    logger.warning("Node.js is not installed.")
    logger.debug("Installing the latest version of Node.js for macOS...")
    await update_progress(0.1, "Get Node.js installation resources")
    await asyncio.sleep(2)
    await update_progress(0.3, "Please be patient and wait...")
    try:
        result = subprocess.run(["brew", "install", "node"], capture_output=True, startupinfo=startupinfo)
        if result.returncode == 0:
            logger.debug("Node.js installation was successful. Restart for changes to take effect.")
            return True
        else:
            logger.error("Node.js installation failed")
            raise Exception("Please manually install by yourself")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Node.js using Homebrew. {e}")
        logger.error("Please install Node.js manually or check your Homebrew installation.")
        raise Exception("Please check if Homebrew has been installed") from None
    except Exception as e:
        logger.error(f"Node.js installation failed, {e}")
        raise RuntimeError("Node.js install failed") from None


def get_package_manager():
    dist_id = distro.id()
    if dist_id in ["centos", "fedora", "rhel", "amzn", "oracle", "scientific", "opencloudos", "alinux"]:
        return "RHS"
    else:
        return "DBS"


async def install_nodejs(update_progress) -> bool:
    if current_platform == "Windows":
        return await install_nodejs_windows(update_progress)
    elif current_platform == "Linux":
        os_type = get_package_manager()
        if os_type == "RHS":
            return await install_nodejs_centos(update_progress)
        else:
            return await install_nodejs_ubuntu(update_progress)
    elif current_platform == "Darwin":
        return await install_nodejs_mac(update_progress)
    else:
        logger.debug(
            f"Node.js auto installation is not supported on this platform: {current_platform}. "
            f"Please install Node.js manually."
        )
        return False


def update_env_path():
    current_env_path = os.environ.get("PATH")
    if current_platform != "Windows":
        path_list = ["/usr/bin/", "/usr/local/bin", "/opt/homebrew/bin"]
        current_env_path_list = current_env_path.split(os.pathsep)
        env_path = [path for path in path_list if path not in set(current_env_path_list)]
        node_env_path = os.pathsep.join([node_path] + env_path + current_env_path_list)
    else:
        node_env_path = node_path + os.pathsep + current_env_path
    os.environ["PATH"] = node_env_path


async def check_nodejs_installed() -> bool:
    try:
        update_env_path()
        result = subprocess.run(["node", "-v"], capture_output=True, startupinfo=startupinfo, text=True)
        logger.info(result)
        version_info = result.stdout.strip()
        if result.returncode == 0 and version_info:
            return True
    except FileNotFoundError as e:
        logger.info(e)
    return False
