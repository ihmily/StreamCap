import asyncio
import json
import os
from typing import Any

import flet as ft
import httpx

from ...utils.logger import logger


class UpdateChecker:
    def __init__(self, app):
        self.app = app
        self.current_version = self._get_current_version()
        self.update_config = self._load_update_config()
        
    def _get_current_version(self) -> str:
        try:
            config_path = os.path.join(self.app.run_path, "config", "version.json")
            with open(config_path, encoding="utf-8") as f:
                version_data = json.load(f)
                return version_data["version_updates"][0]["version"]
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return "0.0.0"

    @staticmethod
    def _load_update_config() -> dict[str, Any]:
        auto_check = os.getenv("AUTO_CHECK_UPDATE", "false").lower() == "true"
        update_source = os.getenv("UPDATE_SOURCE", "both").lower()
        github_repo = os.getenv("GITHUB_REPO", "ihmily/StreamCap")
        custom_api = os.getenv("CUSTOM_UPDATE_API", "")
        check_interval = int(os.getenv("UPDATE_CHECK_INTERVAL", "86400"))
        
        update_sources = []
        
        if update_source in ["github", "both"]:
            update_sources.append({
                "name": "GitHub",
                "enabled": True,
                "priority": 1 if update_source == "github" else 0,
                "type": "github",
                "repo": github_repo,
                "timeout": 10
            })
        
        if update_source in ["custom", "both"] and custom_api:
            update_sources.append({
                "name": "Custom",
                "enabled": True,
                "priority": 1 if update_source == "custom" else 2,
                "type": "custom",
                "url": custom_api,
                "timeout": 5
            })
        
        return {
            "update_sources": update_sources,
            "check_interval": check_interval,
            "auto_check": auto_check
        }
    
    async def check_for_updates(self) -> dict[str, Any]:
        """Check for updates, prioritizing sources with higher priority"""
        sources = sorted(
            [s for s in self.update_config["update_sources"] if s["enabled"]],
            key=lambda x: x["priority"],
            reverse=True
        )
        
        if not sources:
            logger.warning("No available update sources configured")
            return {"has_update": False, "error": "No available update sources configured"}
        
        tasks = []
        for source in sources:
            if source["type"] == "github":
                tasks.append(self._check_github_update(source))
            elif source["type"] == "custom":
                tasks.append(self._check_custom_update(source))
        
        # Wait for any task to complete successfully or all to fail
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result["has_update"] or "error" not in result:
                    return result
                results.append(result)
            except Exception as e:
                logger.error(f"Update check failed: {e}")
                results.append({"has_update": False, "error": str(e)})
        
        return results[-1] if results else {"has_update": False, "error": "All update sources check failed"}
    
    async def _check_github_update(self, source: dict[str, Any]) -> dict[str, Any]:
        """Check for updates from GitHub"""
        try:
            timeout = httpx.Timeout(source["timeout"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    "https://api.github.com/repos/" + source['repo'] + "/releases/latest"
                )

                if response.status_code == 200:
                    latest_release = response.json()
                    latest_version = latest_release["tag_name"].lstrip("v")
                    
                    if self._compare_versions(latest_version, self.current_version) > 0:
                        download_urls = {}
                        for asset in latest_release.get("assets", []):
                            name = asset["name"].lower()
                            if ("win" in name or "windows" in name) and "noff" not in name:
                                download_urls["windows"] = asset["browser_download_url"]
                            elif ("mac" in name or "macos" in name) and "noff" not in name:
                                download_urls["macos"] = asset["browser_download_url"]
                            elif "linux" in name:
                                download_urls["linux"] = latest_release["html_url"]
                        
                        return {
                            "has_update": True,
                            "latest_version": latest_version,
                            "current_version": self.current_version,
                            "release_notes": latest_release["body"],
                            "download_url": latest_release["html_url"],
                            "download_urls": download_urls,
                            "source": source["name"]
                        }
                return {"has_update": False, "source": source["name"]}
        except Exception as e:
            logger.error(f"Failed to check update from GitHub: {e}")
            return {"has_update": False, "error": str(e), "source": source["name"]}
    
    async def _check_custom_update(self, source: dict[str, Any]) -> dict[str, Any]:
        """Check for updates from custom source
        
        Expected API Response Format:
        {
            "has_update": bool,           # Whether there is a new version available
            "latest_version": str,        # Latest version number (e.g. "1.0.0")
            "current_version": str,       # Current version number
            "release_notes": str,         # Release notes or update description
            "download_url": str,          # Main download page URL
            "download_urls": {            # Optional: Platform-specific download URLs
                "windows": str,           # Windows download URL
                "macos": str,            # macOS download URL
                "linux": str             # Linux download URL
            }
        }
        """
        try:
            timeout = httpx.Timeout(source["timeout"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    source["url"],
                    params={"current_version": self.current_version}
                )
                if response.status_code == 200:
                    update_info = response.json()
                    if update_info.get("has_update", False):
                        return {
                            **update_info,
                            "source": source["name"]
                        }
                    return {"has_update": False, "source": source["name"]}
                return {"has_update": False, "error": f"API returned status code: {response.status_code}",
                        "source": source["name"]}
        except Exception as e:
            logger.error(f"Failed to check update from custom source: {e}")
            return {"has_update": False, "error": str(e), "source": source["name"]}

    @staticmethod
    def _compare_versions(version1: str, version2: str) -> int:
        """Compare version numbers, returns 1 if version1 > version2, 0 if equal, -1 if less"""
 
        def parse_version(version):
            if "-" in version:
                v_parts, pre_release = version.split("-", 1)
                pre_release_value = 0
                if pre_release == "alpha":
                    pre_release_value = -3
                elif pre_release == "beta":
                    pre_release_value = -2
                elif pre_release == "rc":
                    pre_release_value = -1
            else:
                v_parts = version
                pre_release_value = 0
            
            v_nums = []
            for part in v_parts.split("."):
                try:
                    v_nums.append(int(part))
                except ValueError:
                    for ii, c in enumerate(part):
                        if not c.isdigit():
                            try:
                                v_nums.append(int(part[:ii]))
                            except ValueError:
                                v_nums.append(0)
                            break
            
            return v_nums, pre_release_value
        
        v1_parts, v1_pre = parse_version(version1)
        v2_parts, v2_pre = parse_version(version2)
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        
        if v1_pre > v2_pre:
            return 1
        elif v1_pre < v2_pre:
            return -1
        
        return 0
    
    async def show_update_dialog(self, update_info: dict[str, Any]) -> None:
        _ = self.app.language_manager.language.get("update", {})

        dialog = ft.AlertDialog(
            title=ft.Text(_["new_version"].format(version=update_info.get("latest_version"))),
            content=ft.Column([
                ft.Text(_["current_version"].format(version=update_info.get("current_version"))),
                ft.Text(_["latest_version"].format(version=update_info.get("latest_version"))),
                ft.Text(_["update_source"].format(source=update_info.get("source", _["unknown"]))),
            ], spacing=10, width=400, height=300),
            actions=[
                ft.TextButton(_["later"], on_click=lambda _: self.close_dialog()),
                ft.TextButton(_["download"], on_click=lambda _: self.open_download_page(update_info))
            ],
        )

        self.app.dialog_area.content = dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()
    
    def close_dialog(self) -> None:
        if self.app.dialog_area.content:
            self.app.dialog_area.content.open = False
            self.app.dialog_area.update()

    def open_download_page(self, update_info: dict[str, Any]) -> None:
        import platform

        url = update_info.get("download_url", "https://github.com/ihmily/StreamCap/releases/latest")
        
        download_urls = update_info.get("download_urls", {})
        if download_urls:
            system = platform.system().lower()
            if system == "windows" and "windows" in download_urls:
                url = download_urls["windows"]
            elif system == "darwin" and "macos" in download_urls:
                url = download_urls["macos"]
            elif system == "linux" and "linux" in download_urls:
                url = download_urls["linux"]
        
        self.app.page.launch_url(url)
        self.close_dialog()
