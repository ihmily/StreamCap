import flet as ft


class SaveProgressOverlay:
    def __init__(self, app):
        self.app = app
        self._ = {}
        self.app.language_manager.add_observer(self)
        self.load()
        
        self.message_text = None
        self.cancel_button = None
        self.warning_text = None
        self.progress_ring = None
        self.simple_progress_ring = None
        self.content_container = None
        self.simple_container = None
        self.overlay = ft.Stack([], visible=False)
        
        self.is_cancellable = False
        self.is_simple_mode = False
        self._initialized = False
        
    def _initialize_components(self):
        if self._initialized:
            return
            
        self.message_text = ft.Text(
            self._["saving_recording"], 
            size=18, 
            weight=ft.FontWeight.W_500,
            color=ft.colors.WHITE,
            text_align=ft.TextAlign.CENTER
        )
        
        self.cancel_button = ft.ElevatedButton(
            text=f"😾 {self._['force_close']}",
            on_click=self._on_force_close,
            style=ft.ButtonStyle(
                color=ft.colors.WHITE,
                bgcolor="#FF5252",
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=0,
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
            ),
            tooltip=self._["force_close_tooltip"],
            visible=False
        )
        
        self.warning_text = ft.Text(
            self._["force_close_warning"],
            size=12,
            color=ft.colors.with_opacity(0.7, ft.colors.WHITE),
            text_align=ft.TextAlign.CENTER,
            visible=False
        )
        
        self.progress_ring = ft.ProgressRing(
            width=60, 
            height=60, 
            stroke_width=4,
            color="#2196F3",
            value=0.7
        )
        
        self.simple_progress_ring = ft.ProgressRing(
            width=50, 
            height=50, 
            stroke_width=3,
            color="#2196F3",
            value=0.8
        )
        
        self.content_container = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=self.progress_ring,
                        margin=ft.margin.only(bottom=20)
                    ),
                    self.message_text,
                    ft.Container(height=25),
                    self.cancel_button,
                    ft.Container(height=8),
                    self.warning_text
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            ),
            width=400,
            height=280,
            padding=ft.padding.all(30),
            alignment=ft.alignment.center,
            bgcolor=ft.colors.with_opacity(0.95, "#212121"),
            border_radius=16,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=24,
                color=ft.colors.with_opacity(0.5, ft.colors.BLACK),
                offset=ft.Offset(0, 4)
            ),
        )
        
        self.simple_container = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=self.simple_progress_ring,
                        margin=ft.margin.only(bottom=15)
                    ),
                    self.message_text,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            ),
            width=300,
            height=180,
            padding=ft.padding.all(25),
            alignment=ft.alignment.center,
            bgcolor=ft.colors.with_opacity(0.95, "#212121"),
            border_radius=16,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=24,
                color=ft.colors.with_opacity(0.5, ft.colors.BLACK),
                offset=ft.Offset(0, 4)
            ),
        )
        
        self.overlay.controls = [
            ft.Container(
                content=self.content_container,
                alignment=ft.alignment.center,
                expand=True,
                bgcolor=ft.colors.with_opacity(0.7, ft.colors.BLACK),
                animate_opacity=300,
            )
        ]
        
        self._initialized = True
        
    def _on_force_close(self, e):
        self.message_text.value = self._["force_closing"]
        self.cancel_button.visible = False
        self.warning_text.visible = False
        self.overlay.update()

        self.app.page.window.destroy()

    def show(self, message=None, cancellable=False):
        self._initialize_components()
        
        if message:
            self.message_text.value = message
        else:
            self.message_text.value = self._["saving_recording"]
            
        self.is_cancellable = cancellable
        
        if cancellable:
            self.is_simple_mode = False
            self.overlay.controls[0].content = self.content_container
            self.cancel_button.visible = True
            self.warning_text.visible = True
        else:
            self.is_simple_mode = True
            self.overlay.controls[0].content = self.simple_container
            self.cancel_button.visible = False
            self.warning_text.visible = False
            
        self.overlay.visible = True
        self.overlay.update()

    def update_message(self, message):
        if self._initialized:
            self.message_text.value = message
            self.message_text.update()
        
    def show_cancel_button(self):
        if not self._initialized:
            return
            
        if not self.cancel_button.visible and not self.is_simple_mode:
            self.cancel_button.visible = True
            self.warning_text.visible = True
            self.cancel_button.update()
            self.warning_text.update()

    def hide(self):
        self.overlay.visible = False
        self.overlay.update()

    def load(self):
        self._ = self.app.language_manager.language.get("save_progress_overlay", {})

    @property
    def visible(self):
        return self.overlay.visible 