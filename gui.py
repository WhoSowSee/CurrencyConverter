import customtkinter as ctk
import threading
import sys
from core import CurrencyConverterCore, format_number

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ManualRateDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.result = None

        self.title("Ручной ввод курса")
        self.geometry("350x190")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        dialog_w, dialog_h = 350, 190
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

        ctk.CTkLabel(
            self, text="Введите курс UAH к RUB", font=ctk.CTkFont(size=15)
        ).pack(pady=(20, 10), padx=20)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Введите число...",
            font=ctk.CTkFont(size=14),
            width=200,
        )
        self.entry.pack(pady=5, padx=20)
        self.entry.focus()
        self.entry.bind("<KeyPress>", self._handle_key_press)
        self.entry.bind("<KeyRelease>", self._validate_input)
        self.entry.bind("<Return>", self._on_ok)

        self.error_label = ctk.CTkLabel(
            self, text="", text_color="#FF6B6B", font=ctk.CTkFont(size=14)
        )
        self.error_label.pack(pady=(0, 5), padx=20)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkButton(btn_frame, text="Ок", command=self._on_ok).pack(
            side="left", expand=True, padx=(0, 5)
        )
        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            command=self._on_cancel,
            fg_color="#555",
            hover_color="#666",
        ).pack(side="right", expand=True, padx=(5, 0))

    def _handle_key_press(self, event):
        if event.state & 4 and event.keysym.lower() == 'a':
            event.widget.select_range(0, 'end')
            return "break"

    def _validate_input(self, event=None) -> bool:
        if event and event.state & 4 and event.keysym.lower() == 'a':
            return True

        value_str = self.entry.get().strip().replace(',', '.')

        if not value_str:
            self.error_label.configure(text="")
            return False

        try:
            value = float(value_str)
            if value <= 0:
                self.error_label.configure(
                    text="❌ Значение должно быть больше нуля"
                )
                return False
            self.error_label.configure(text="")
            return True
        except (ValueError, TypeError):
            self.error_label.configure(text="❌ Введите корректное значение")
            return False

    def _on_ok(self, event=None):
        if self._validate_input():
            self.result = float(self.entry.get().strip().replace(',', '.'))
            self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def get_value(self) -> float | None:
        self.parent.wait_window(self)
        return self.result


class ModernCurrencyConverterGUI:
    def __init__(self, force_manual_mode=False):
        self.converter = CurrencyConverterCore()
        self.conversion_timer = None
        self.force_manual_mode = force_manual_mode

        self.root = ctk.CTk()
        self.root.title("Конвертер валют")
        self.root.geometry("650x645")
        self.root.resizable(False, False)

        self.setup_ui()
        if not self.force_manual_mode:
            self.refresh_rates_threaded(is_initial_load=True)

    def handle_key_press(self, event):
        if event.state & 4 and event.keysym.lower() == 'a':
            event.widget.select_range(0, 'end')
            return "break"

    def setup_ui(self):
        self.rate_label = ctk.CTkLabel(
            self.root, text="🔄 Загрузка курса...", font=ctk.CTkFont(size=16)
        )
        self.rate_label.pack(pady=(30, 10))

        self.status_label = ctk.CTkLabel(
            self.root,
            text="🔄 Проверка соединения...",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.status_label.pack(pady=(0, 5))

        self.manual_rate_button = ctk.CTkButton(
            self.root,
            text="🖊 Ввести курс вручную",
            command=self.prompt_for_manual_rate,
            fg_color="#555555",
            hover_color="#666666",
        )

        input_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        input_frame.pack(fill='x', padx=30, pady=(15, 30))

        self.amount_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Введите сумму...",
            font=ctk.CTkFont(size=16),
            height=40,
        )
        self.amount_entry.pack(
            side='left', padx=(0, 10), fill='x', expand=True
        )
        self.amount_entry.bind('<KeyRelease>', self.on_amount_change)
        self.amount_entry.bind("<KeyPress>", self.handle_key_press)

        self.refresh_btn = ctk.CTkButton(
            input_frame,
            text="🔄",
            width=50,
            height=40,
            command=self.refresh_rates_threaded,
            font=ctk.CTkFont(size=18),
        )
        self.refresh_btn.pack(side='right')

        self._setup_conversion_frames()

    def _setup_conversion_frames(self):
        normal_frame = ctk.CTkFrame(self.root)
        normal_frame.pack(fill='x', padx=30, pady=(0, 20))
        ctk.CTkLabel(
            normal_frame,
            text="Обычная конвертация",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(15, 10))
        radio_frame = ctk.CTkFrame(normal_frame, fg_color="transparent")
        radio_frame.pack(pady=(0, 10))
        self.normal_mode = ctk.StringVar(value="uah_to_rub")
        ctk.CTkRadioButton(
            radio_frame,
            text="Гривны → Рубли",
            variable=self.normal_mode,
            value="uah_to_rub",
            command=self.perform_conversion,
            font=ctk.CTkFont(size=14),
        ).pack(side='left', padx=(0, 30))
        ctk.CTkRadioButton(
            radio_frame,
            text="Рубли → Гривны",
            variable=self.normal_mode,
            value="rub_to_uah",
            command=self.perform_conversion,
            font=ctk.CTkFont(size=14),
        ).pack(side='left')
        self.normal_result = ctk.CTkLabel(
            normal_frame,
            text="📊 Результат: ",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.normal_result.pack(pady=(10, 15))

        steam_toggle_frame = ctk.CTkFrame(self.root)
        steam_toggle_frame.pack(fill='x', padx=30, pady=(0, 10))
        self.steam_checkbox = ctk.CTkCheckBox(
            steam_toggle_frame,
            text="Включить режим Steam пополнения",
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.toggle_steam_mode,
            text_color="#1f9eff",
        )
        self.steam_checkbox.pack(pady=15)

        self.steam_frame = ctk.CTkFrame(self.root)
        ctk.CTkLabel(
            self.steam_frame,
            text="Steam пополнение",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(15, 10))
        steam_radio_frame = ctk.CTkFrame(
            self.steam_frame, fg_color="transparent"
        )
        steam_radio_frame.pack(pady=(0, 10))
        self.steam_mode = ctk.StringVar(value="rub_to_steam_rub")
        ctk.CTkRadioButton(
            steam_radio_frame,
            text="Рубли → Steam RUB",
            variable=self.steam_mode,
            value="rub_to_steam_rub",
            command=self.perform_conversion_delayed,
            font=ctk.CTkFont(size=14),
        ).pack(side='left', padx=(0, 30))
        ctk.CTkRadioButton(
            steam_radio_frame,
            text="Гривны → Steam RUB",
            variable=self.steam_mode,
            value="uah_to_steam_rub",
            command=self.perform_conversion_delayed,
            font=ctk.CTkFont(size=14),
        ).pack(side='left')
        self.steam_result = ctk.CTkLabel(
            self.steam_frame,
            text="🎮 Steam результат: ",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#1f9eff",
        )
        self.steam_result.pack(pady=(10, 5))
        self.commission_label = ctk.CTkLabel(
            self.steam_frame,
            text="💸 Комиссия: ",
            font=ctk.CTkFont(size=13),
            text_color="#999999",
        )
        self.commission_label.pack(pady=(0, 15))

    def on_amount_change(self, event=None):
        self.perform_conversion_delayed()

    def perform_conversion_delayed(self):
        if self.conversion_timer:
            self.root.after_cancel(self.conversion_timer)
        self.conversion_timer = self.root.after(300, self.perform_conversion)

    def perform_conversion(self):
        amount_text = self.amount_entry.get().strip().replace(',', '.')
        if not amount_text:
            self._clear_results()
            return
        try:
            amount = float(amount_text)
            if amount <= 0:
                self._show_error("❌ Значение должно быть больше нуля")
                return
        except ValueError:
            self._show_error("❌ Введите корректное значение")
            return

        is_reverse = self.normal_mode.get() == "rub_to_uah"
        result = self.converter.convert_currency(amount, reverse=is_reverse)
        if "error" in result:
            self.normal_result.configure(
                text=f"📊 Результат: {result['error']}"
            )
        else:
            to_symbol = "₴" if is_reverse else "₽"
            self.normal_result.configure(
                text=f"📊 Результат: {result['result']}{to_symbol}"
            )

        if self.steam_checkbox.get():
            self._perform_steam_conversion(amount)

    def _perform_steam_conversion(self, amount: float):
        self.steam_result.configure(text="🎮 Steam результат: ⏳")
        self.commission_label.configure(text="💸 Комиссия: ⏳")

        def task():
            is_from_uah = self.steam_mode.get() == "uah_to_steam_rub"
            res = self.converter.convert_to_steam(amount, from_uah=is_from_uah)
            self.root.after(0, self._update_steam_ui, res, amount)

        threading.Thread(target=task, daemon=True).start()

    def _update_steam_ui(self, result: dict, amount: float):
        if "error" in result:
            self.steam_result.configure(
                text=f"🎮 Steam результат: {result['error']}"
            )
            self.commission_label.configure(text="💸 Комиссия: -")
            return

        self.steam_result.configure(
            text=f"🎮 Steam результат: {result['steam_result']}₽"
        )

        comm_text = f"💸 Комиссия: {result['commission_amount']}₽ ({result['commission']}%)"
        if result['from_currency'] == 'UAH':
            comm_text += f" | Заплатите: {format_number(amount)}₴ ({format_number(result['rub_amount'])}₽)"
        else:
            comm_text += f" | Заплатите: {format_number(amount)}₽"
        self.commission_label.configure(text=comm_text)

    def toggle_steam_mode(self):
        if self.steam_checkbox.get():
            self.steam_frame.pack(fill='x', padx=30, pady=(0, 20))
            self.perform_conversion()
        else:
            self.steam_frame.pack_forget()

    def refresh_rates_threaded(self, is_initial_load=False):
        if not is_initial_load:
            self.refresh_btn.configure(text="⏳", state='disabled')
        threading.Thread(
            target=self._refresh_task, args=(is_initial_load,), daemon=True
        ).start()

    def _refresh_task(self, is_initial_load: bool):
        if not is_initial_load:
            self.converter.cache_manager.reload_from_disk()

        self.converter.initialize()
        self.root.after(0, self._update_ui_after_refresh, is_initial_load)

    def _update_ui_after_refresh(self, is_initial_load: bool):
        status = self.converter.get_status_info()
        self.manual_rate_button.pack_forget()
        default_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]

        if status['rate_source'] == 'api':
            success_color = "#4CAF50"
            self.rate_label.configure(text=f"📈 {status['rate_display']}")
            if not is_initial_load:
                self.rate_label.configure(text_color=success_color)
                self.root.after(
                    2000,
                    lambda: self.rate_label.configure(
                        text_color=default_color
                    ),
                )
            else:
                self.rate_label.configure(text_color=default_color)
        elif status['rate_source'] == 'cache':
            self.rate_label.configure(
                text=f"💾 {status['rate_display']}", text_color="#FF9500"
            )
        elif status['rate_source'] == 'manual':
            self.rate_label.configure(
                text=f"🖊 {status['rate_display']}", text_color="#1f9eff"
            )
        elif status['rate_source'] == 'default':
            self.rate_label.configure(
                text=f"📌 {status['rate_display']}", text_color="#FF6B6B"
            )

        if self.force_manual_mode or status['rate_source'] in [
            'default',
            'manual',
        ]:
            self.manual_rate_button.pack(
                before=self.amount_entry.master, pady=(0, 15)
            )

        status_text = (
            "🟢 Онлайн | 📈 Актуальные данные"
            if status['is_online']
            else f"🔴 Офлайн | 💾 Кэш ({status.get('cache_age', 'N/A')})"
        )
        if status['rate_source'] == 'default':
            status_text = "🔴 Офлайн | 📌 Данные по умолчанию"
        elif status['rate_source'] == 'manual':
            status_text = "🔴 Офлайн | 🖊 Ручной ввод"
        self.status_label.configure(text=status_text)

        self.perform_conversion()
        if not is_initial_load:
            self.refresh_btn.configure(text="🔄", state='normal')

    def prompt_for_manual_rate(self, exit_on_cancel=False):
        dialog = ManualRateDialog(self.root)
        rate = dialog.get_value()

        if rate is not None:
            self.converter.set_manual_rate(rate)
            self._update_ui_after_refresh(is_initial_load=False)
        elif exit_on_cancel:
            print("Запуск отменен: курс не был введен", file=sys.stderr)
            sys.exit(0)

    def _clear_results(self):
        self.normal_result.configure(text="📊 Результат: ")
        if self.steam_checkbox.get():
            self.steam_result.configure(text="🎮 Steam результат: ")
            self.commission_label.configure(text="💸 Комиссия: ")

    def _show_error(self, message: str):
        self.normal_result.configure(text=message)
        if self.steam_checkbox.get():
            self.steam_result.configure(text=message)
            self.commission_label.configure(text="💸 Комиссия: ✖️")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    force_manual_mode = any(arg in ['-m', '--manual-rate'] for arg in sys.argv)
    app = ModernCurrencyConverterGUI(force_manual_mode=force_manual_mode)

    if app.force_manual_mode:
        app.prompt_for_manual_rate(exit_on_cancel=True)

    other_args = [
        arg for arg in sys.argv[1:] if arg not in ['-m', '--manual-rate']
    ]

    for arg in other_args:
        if arg.replace('.', '', 1).isdigit():
            app.amount_entry.insert(0, str(format_number(float(arg))))
        elif arg in ['-r', '--reverse']:
            app.normal_mode.set("rub_to_uah")
        elif arg in ['-s', '--steam']:
            app.steam_checkbox.select()
            app.toggle_steam_mode()
        elif arg in ['-sr', '--steamreverse']:
            app.steam_checkbox.select()
            app.toggle_steam_mode()
            app.steam_mode.set("uah_to_steam_rub")

    if app.amount_entry.get():
        app.perform_conversion()

    app.run()
