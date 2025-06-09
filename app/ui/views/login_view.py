from typing import Callable

import flet as ft

from ...auth.auth_manager import AuthManager
from ...utils.logger import logger


class LoginPage:
    
    def __init__(self, page: ft.Page, auth_manager: AuthManager, on_login_success: Callable):
        self.page = page
        self.auth_manager = auth_manager
        self.on_login_success = on_login_success
        
        app = auth_manager.app
        language = app.language_manager.language
        self._ = language.get("login_page", {})
        
        self.page.title = self._["login_title"]
        
        self.username_field = ft.TextField(
            label=self._["username"],
            autofocus=True,
            width=320,
            border_radius=8,
            prefix_icon=ft.icons.PERSON,
            focused_border_color="#0078d4",
            focused_color="#0078d4",
            border_color="#d0d0d0",
            bgcolor="#f5f5f5",
            color="#333333",
            label_style=ft.TextStyle(color="#666666"),
        )
        
        self.password_field = ft.TextField(
            label=self._["password"],
            password=True,
            can_reveal_password=True,
            width=320,
            border_radius=8,
            prefix_icon=ft.icons.LOCK_OUTLINE,
            focused_border_color="#0078d4",
            focused_color="#0078d4",
            border_color="#d0d0d0",
            bgcolor="#f5f5f5",
            color="#333333",
            label_style=ft.TextStyle(color="#666666"),
        )
        
        self.login_button = ft.ElevatedButton(
            text=self._["login_button"],
            width=320,
            on_click=self.handle_login,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                color="#ffffff",
                bgcolor="#0078d4",
                elevation=0,
                padding=15,
                animation_duration=300,
            ),
        )
        
        self.error_text = ft.Text(
            color=ft.colors.RED_500,
            size=14,
            visible=False,
        )
        
        self.logo = ft.Image(
            src="/icons/loading-animation.png",
            width=80,
            height=80,
            fit=ft.ImageFit.CONTAIN,
        )
        
        login_card_content = ft.Column(
            controls=[
                ft.Container(
                    content=self.logo,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(bottom=10),
                ),
                ft.Text(
                    "StreamCap", 
                    size=28, 
                    weight=ft.FontWeight.BOLD,
                    color="#0078d4",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    self._["login_subtitle"],
                    size=16,
                    color="#666666",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=20),
                self.username_field,
                ft.Container(height=10),
                self.password_field,
                ft.Container(
                    content=self.error_text,
                    margin=ft.margin.only(top=10),
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=20),
                self.login_button,
                ft.Container(height=10),
                ft.Text(
                    self._["default_account_tip"],
                    size=12,
                    color="#999999",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5,
        )
        
        self.login_card = ft.Container(
            content=login_card_content,
            width=400,
            height=600,
            padding=30,
            bgcolor=ft.colors.WHITE,
            border_radius=12,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.colors.with_opacity(0.1, "#000000"),
                offset=ft.Offset(0, 4),
            ),
        )
        
        self.main_view = ft.Container(
            content=self.login_card,
            alignment=ft.alignment.center,
            expand=True,
            bgcolor="#f0f2f5",
        )
    
    async def handle_login(self, e):
        username = self.username_field.value
        password = self.password_field.value
        
        if not username or not password:
            self.show_error(self._["input_required"])
            return
        
        original_text = self.login_button.text
        self.login_button.text = self._["login_in_progress"]
        self.login_button.disabled = True
        self.page.update()
        
        success, token = await self.auth_manager.authenticate(username, password)
        
        self.login_button.text = original_text
        self.login_button.disabled = False
        self.page.update()
        
        if success:
            logger.info(f"Login successful: {username}")
            await self.page.client_storage.set_async("session_token", token)
            await self.on_login_success(token)
        else:
            self.show_error(self._["login_failed"])
    
    def show_error(self, message: str):
        self.error_text.value = message
        self.error_text.visible = True
        self.page.update()
    
    def clear_error(self):
        self.error_text.visible = False
        self.page.update()
    
    def get_view(self) -> ft.Control:
        return self.main_view 