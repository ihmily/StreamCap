import asyncio
import os
import platform
import re
import subprocess
import sys
import zipfile
from pathlib import Path
import shutil

import httpx

from ..utils.logger import logger
from ..utils.utils import get_startup_info

current_platform = platform.system()
execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]
ffmpeg_path = os.path.join(execute_dir, "ffmpeg")
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


async def get_lanzou_download_link(url: str, password: str | None = None, headers: dict | None = None) -> str | None:
    try:

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=headers)
            html_str = response.text
            sign_match = re.search("var \\w+ = '([A-Za-z0-9_\\-+/]{80,})';", html_str)
            if not sign_match:
                return None
            sign = sign_match.group(1)

            data = {
                "action": "downprocess",
                "p": password,
                "sign": sign,
                "kd": "1",
            }

            response = await client.post(
                "https://wweb.lanzoum.com/ajaxm.php?file=219989236",
                headers=headers,
                data=data
            )
            json_data = response.json()
            download_url = json_data["dom"] + "/file/" + json_data["url"]
            response = await client.get(download_url, headers=headers, follow_redirects=True)
            return str(response.url)
    except Exception as e:
        logger.error(f"Failed to obtain ffmpeg download address. {e}")


def _iter_possible_ffmpeg_bin_dirs(root_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for child in root_dir.iterdir():
        if not child.is_dir():
            continue
        bin_dir = child / "bin"
        if (bin_dir / "ffmpeg.exe").exists():
            candidates.append(bin_dir)
    return candidates


def _normalize_windows_ffmpeg_layout(root_dir: Path) -> bool:
    ffmpeg_dir = root_dir / "ffmpeg"
    if (ffmpeg_dir / "ffmpeg.exe").exists():
        return True

    if (ffmpeg_dir / "bin" / "ffmpeg.exe").exists():
        bin_dir = ffmpeg_dir / "bin"
        for item in bin_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, ffmpeg_dir / item.name)
        return (ffmpeg_dir / "ffmpeg.exe").exists()

    candidates = _iter_possible_ffmpeg_bin_dirs(root_dir)
    if not candidates:
        return False

    bin_dir = candidates[0]
    if ffmpeg_dir.exists():
        shutil.rmtree(ffmpeg_dir, ignore_errors=True)
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)
    for item in bin_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, ffmpeg_dir / item.name)
    return (ffmpeg_dir / "ffmpeg.exe").exists()


async def _download_file(url: str, dest_path: Path, headers: dict | None, update_progress) -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Download failed: {resp.status_code}")

            total_size = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = 0.2 + 0.6 * (downloaded / total_size)
                        await update_progress(
                            round(progress, 2),
                            f"Downloading... {downloaded // 1024}KB/{total_size // 1024}KB",
                        )
                    else:
                        await update_progress(0.5, f"Downloading... {downloaded // 1024}KB")


async def install_ffmpeg_windows(update_progress):
    try:
        logger.warning("ffmpeg is not installed.")
        logger.debug("Installing the latest version of ffmpeg for Windows...")
        await update_progress(0.1, "Get FFmpeg installation resources")

        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            )
        }

        download_candidates = [
            ("gyan", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
            ("btbn", "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"),
        ]

        ffmpeg_url = None
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            for _name, url in download_candidates:
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        ffmpeg_url = str(resp.url)
                        break
                except Exception:
                    continue

        if not ffmpeg_url:
            lanzou_headers = {
                "content-type": "application/x-www-form-urlencoded",
                "accept-language": "zh-CN,zh;q=0.9",
                "origin": "https://wweb.lanzoum.com",
                "referer": "https://wweb.lanzoum.com/iHAc22ly3r3g",
                "user-agent": headers["user-agent"],
                "x-requested-with": "XMLHttpRequest",
            }
            ffmpeg_url = await get_lanzou_download_link("https://wweb.lanzoum.com/iHAc22ly3r3g", "eots", lanzou_headers)
            headers = lanzou_headers

        if not ffmpeg_url:
            logger.error("Please manually install ffmpeg by yourself")
            raise Exception("Failed to obtain the FFmpeg download address")

        zip_file_path = Path(execute_dir) / "ffmpeg_latest_build.zip"
        if zip_file_path.exists():
            await update_progress(0.2, "FFmpeg installation file already exists")
        else:
            await update_progress(0.2, "Start downloading FFmpeg installation package")
            logger.debug(f"FFmpeg Download: {ffmpeg_url}")
            await _download_file(ffmpeg_url, zip_file_path, headers, update_progress)

        await update_progress(0.8, "Extracting and cleaning installation files")
        await unzip_file(zip_file_path, execute_dir)
        if not _normalize_windows_ffmpeg_layout(Path(execute_dir)):
            raise Exception("FFmpeg files extracted but layout is unexpected")

        await update_progress(0.9, "Configuring FFmpeg environment variables")
        update_env_path()
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, startupinfo=startupinfo)
        if result.returncode == 0:
            logger.success("FFmpeg installation was successful")
            return True

        logger.error("ffmpeg installation failed. Please manually install ffmpeg by yourself")
        raise Exception("Please restart the program")
    except Exception as e:
        raise RuntimeError(f"FFmpeg install failed, {e}") from None


async def install_ffmpeg_mac(update_progress):
    logger.warning("FFmpeg is not installed.")
    logger.debug("Installing the stable version of ffmpeg for macOS...")
    await update_progress(0.1, "Get FFmpeg installation resources")
    await asyncio.sleep(2)
    await update_progress(0.3, "Please be patient and wait...")
    timeout = 300
    try:
        result = subprocess.run(["brew", "install", "ffmpeg"], capture_output=True,
                                startupinfo=startupinfo, timeout=timeout)
        if result.returncode == 0:
            logger.success("FFmpeg installation was successful. Restart for changes to take effect.")
            return True
        else:
            logger.error("FFmpeg installation failed")
            raise Exception("Please manually install FFmpeg by yourself")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install ffmpeg using Homebrew. {e}")
        logger.error("Please install ffmpeg manually or check your Homebrew installation.")
        raise Exception("Please check if Homebrew has been installed") from None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise Exception(e) from None


async def install_ffmpeg_linux(update_progress):
    is_rhs = True
    timeout = 180

    try:
        logger.warning("ffmpeg is not installed.")
        logger.debug("Trying to install the stable version of ffmpeg")
        await update_progress(0.1, "Get FFmpeg installation resources")
        try:
            result = subprocess.run(["yum", "-y", "update"], capture_output=True,
                                    startupinfo=startupinfo, timeout=timeout)
            if result.returncode != 0:
                logger.error("Failed to update package lists using yum.")
                return False

            result = subprocess.run(["yum", "install", "-y", "ffmpeg"], capture_output=True,
                                    startupinfo=startupinfo, timeout=timeout)
            if result.returncode == 0:
                logger.success("ffmpeg installation was successful using yum. Restart for changes to take effect.")
                return True
            logger.error(result.stderr.decode("utf-8").strip())
        except subprocess.TimeoutExpired:
            logger.error("Command execution timed out. Please try to manually install ffmpeg.")
            raise Exception("Command execution timed out after {} seconds".format(timeout))
    except FileNotFoundError:
        logger.error("yum command not found, trying to install using apt...")
        is_rhs = False
    except Exception as e:
        logger.error(f"An error occurred while trying to install ffmpeg using yum: {e}")

    if not is_rhs:
        try:
            logger.debug("Trying to install the stable version of ffmpeg for Linux using apt...")
            try:
                result = subprocess.run(["apt", "update"], capture_output=True,
                                        startupinfo=startupinfo, timeout=timeout)
                if result.returncode != 0:
                    logger.error("Failed to update package lists using apt")
                    return False

                result = subprocess.run(["apt", "install", "-y", "ffmpeg"], capture_output=True,
                                        startupinfo=startupinfo, timeout=timeout)
                if result.returncode == 0:
                    logger.success("ffmpeg installation was successful using apt. Restart for changes to take effect.")
                    return True
                else:
                    logger.error(result.stderr.decode("utf-8").strip())
            except subprocess.TimeoutExpired:
                logger.error("Command execution timed out. Please try to manually install ffmpeg.")
                raise Exception("Command execution timed out after {} seconds".format(timeout))
        except FileNotFoundError:
            logger.error("apt command not found, unable to install ffmpeg. Please manually install ffmpeg by yourself")
        except Exception as e:
            logger.error(f"An error occurred while trying to install ffmpeg using apt: {e}")
    logger.error("Manual installation of ffmpeg is required. Please manually install ffmpeg by yourself.")
    raise Exception("Please manually install FFmpeg by yourself")


async def install_ffmpeg(update_progress) -> bool:
    if current_platform == "Windows":
        return await install_ffmpeg_windows(update_progress)
    elif current_platform == "Linux":
        return await install_ffmpeg_linux(update_progress)
    elif current_platform == "Darwin":
        return await install_ffmpeg_mac(update_progress)
    else:
        logger.warning(
            f"ffmpeg auto installation is not supported on this platform: {current_platform}. Please "
            f"install ffmpeg manually."
        )
    return False


def update_env_path():
    current_env_path = os.environ.get("PATH")
    if current_platform != "Windows":
        path_list = ["/usr/bin/", "/usr/local/bin", "/opt/homebrew/bin"]
        current_env_path_list = current_env_path.split(os.pathsep)
        env_path = [path for path in path_list if path not in set(current_env_path_list)]
        ffmpeg_env_path = os.pathsep.join([ffmpeg_path] + env_path + current_env_path_list)
    else:
        win_paths = []
        if os.path.isdir(os.path.join(ffmpeg_path, "bin")):
            win_paths.append(os.path.join(ffmpeg_path, "bin"))
        win_paths.append(ffmpeg_path)
        ffmpeg_env_path = os.pathsep.join(win_paths + [current_env_path])

    os.environ["PATH"] = ffmpeg_env_path


async def check_ffmpeg_installed() -> bool:
    try:
        update_env_path()
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, startupinfo=startupinfo, text=True)
        version_info = result.stdout.strip()
        if result.returncode == 0 and version_info:
            logger.info(". ".join(version_info.splitlines()[:2]))
            return True
        else:
            logger.debug(result.stderr.strip())
    except FileNotFoundError as e:
        logger.info(e)
    except OSError as e:
        logger.error(f"OSError occurred: {e}.")
        logger.error("Please delete the ffmpeg and try to download and install again.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    return False
