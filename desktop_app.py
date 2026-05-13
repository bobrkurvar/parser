import tkinter as tk
import webbrowser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import logging

# Предполагается, что эти импорты у тебя уже настроены
# from core.logger import setup_logging
# from present import present_job
# from dto import JobPriority

log = logging.getLogger(__name__)


def priority_text(priority) -> str | None:
    # Замени JobPriority на свой класс, если нужно
    if priority.value == 3: return "🔥 HIGH"
    if priority.value == 2: return "⚠️ MEDIUM"
    if priority.value == 1: return "LOW"
    return "HIDDEN"


def priority_tag(priority) -> str:
    if priority.value == 3: return "high"
    if priority.value == 2: return "medium"
    if priority.value == 1: return "low"
    return "hidden"


class App(tk.Tk):
    def __init__(self, backend):
        super().__init__()

        self.title("Freelance Parser")
        self.geometry("1400x800")

        self.jobs = []
        self.selected_job = None
        self.backend = backend

        self.create_widgets()

    def create_widgets(self):
        # =========================
        # Верхняя панель
        # =========================
        top_frame = ttk.Frame(self, padding=8)
        top_frame.pack(fill="x")

        self.load_button = ttk.Button(
            top_frame, text="Загрузить заказы", command=self.start_loading
        )
        self.load_button.pack(side="left")

        self.open_button = ttk.Button(
            top_frame, text="Открыть в браузере", command=self.open_selected_job, state="disabled"
        )
        self.open_button.pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(top_frame, text="Готово")
        self.status_label.pack(side="left", padx=(12, 0))

        # =========================
        # Статистика
        # =========================
        stats_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        stats_frame.pack(fill="x")

        self.all_label = ttk.Label(stats_frame, text="Всего заказов: 0")
        self.all_label.pack(side="left", padx=(0, 20))

        self.passed_label = ttk.Label(stats_frame, text="Прошло: 0")
        self.passed_label.pack(side="left", padx=(0, 20))

        self.content_filtered_label = ttk.Label(stats_frame, text="Отфильтровано контентом: 0")
        self.content_filtered_label.pack(side="left", padx=(0, 20))

        self.stack_filtered_label = ttk.Label(stats_frame, text="Отфильтровано стеком: 0")
        self.stack_filtered_label.pack(side="left", padx=(0, 20))

        # =========================
        # Основная область
        # =========================
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        # ----- Левая панель (Список) -----
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Список заказов").pack(anchor="w", pady=(0, 6))

        columns = ("priority", "title", "date", "feed", "tags")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=25)

        self.tree.tag_configure("high", background="#fff2cc")
        self.tree.tag_configure("medium", background="#e8f4ff")
        self.tree.tag_configure("low", background="#f2f2f2")
        self.tree.tag_configure("hidden", foreground="#999999")  # Для скрытых/закрытых

        self.tree.heading("priority", text="Приоритет")
        self.tree.heading("title", text="Название")
        self.tree.heading("date", text="Дата")
        self.tree.heading("feed", text="Лента")
        self.tree.heading("tags", text="Теги")

        self.tree.column("priority", width=100, anchor="center")
        self.tree.column("title", width=420, anchor="w")
        self.tree.column("date", width=180, anchor="w")
        self.tree.column("feed", width=180, anchor="w")
        self.tree.column("tags", width=220, anchor="w")

        tree_scroll_y = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(left_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.pack(fill="both", expand=True, side="left")
        tree_scroll_y.pack(fill="y", side="right")
        tree_scroll_x.pack(fill="x", side="bottom")

        self.tree.bind("<<TreeviewSelect>>", self.on_job_select)

        # ----- Правая панель (Детали) -----
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Детали заказа").pack(anchor="w", pady=(0, 6))

        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill="x", pady=(0, 8))

        self.title_var = tk.StringVar(value="Название: ")
        self.date_var = tk.StringVar(value="Дата: ")
        self.tags_var = tk.StringVar(value="Теги: ")
        self.url_var = tk.StringVar(value="Ссылка: ")

        ttk.Label(info_frame, textvariable=self.title_var, font=("Segoe UI", 10, "bold"), wraplength=700).pack(
            anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.date_var).pack(anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.tags_var, wraplength=700).pack(anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.url_var, foreground="blue", cursor="hand2").pack(anchor="w", pady=2)

        # =========================
        # ПАНЕЛЬ РАЗМЕТКИ ДЛЯ ML
        # =========================
        self.mark_frame = ttk.LabelFrame(right_frame, text="Разметка заказа (Для обучения ИИ)")
        self.mark_frame.pack(fill="x", pady=(8, 8), padx=4)

        self.mark_var = tk.IntVar(value=-1)
        self.closed_var = tk.BooleanVar(value=False)

        rb_frame = ttk.Frame(self.mark_frame)
        rb_frame.pack(anchor="w", fill="x", padx=5, pady=4)

        ttk.Radiobutton(rb_frame, text="HIDDEN (0)", variable=self.mark_var, value=0).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(rb_frame, text="LOW (1)", variable=self.mark_var, value=1).pack(side="left", padx=10)
        ttk.Radiobutton(rb_frame, text="MEDIUM (2)", variable=self.mark_var, value=2).pack(side="left", padx=10)
        ttk.Radiobutton(rb_frame, text="HIGH (3)", variable=self.mark_var, value=3).pack(side="left", padx=10)

        cb_btn_frame = ttk.Frame(self.mark_frame)
        cb_btn_frame.pack(anchor="w", fill="x", padx=5, pady=(0, 6))

        ttk.Checkbutton(cb_btn_frame, text="Заказ неактуален (Исполнитель найден)", variable=self.closed_var).pack(
            side="left", padx=(0, 20))

        self.save_mark_btn = ttk.Button(cb_btn_frame, text="Сохранить оценку", command=self.save_human_mark,
                                        state="disabled")
        self.save_mark_btn.pack(side="left")

        self.mark_status = ttk.Label(cb_btn_frame, text="", font=("Segoe UI", 9, "bold"))
        self.mark_status.pack(side="left", padx=10)
        # =========================

        ttk.Label(right_frame, text="Описание").pack(anchor="w", pady=(6, 4))

        self.details_text = ScrolledText(right_frame, wrap="word", font=("Consolas", 10))
        self.details_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------------
    # Логика работы UI
    # ------------------------------------------------------------------------
    def start_loading(self):
        self.load_button.config(state="disabled")
        self.open_button.config(state="disabled")
        self.status_label.config(text="Загрузка...")
        self.clear_ui()
        self.backend.collect_and_save(self.on_loading_complete)

    def on_loading_complete(self, result):
        if isinstance(result, Exception):
            self.show_error(result)
        else:
            self.show_result(result)

    def clear_ui(self):
        self.jobs = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.clear_details_panel()

    def clear_details_panel(self):
        """Очищает правую панель (вызывается при удалении/закрытии заказа)"""
        self.selected_job = None
        self.title_var.set("Название: ")
        self.date_var.set("Дата: ")
        self.tags_var.set("Теги: ")
        self.url_var.set("Ссылка: ")
        self.details_text.delete("1.0", tk.END)
        self.mark_var.set(-1)
        self.closed_var.set(False)
        self.save_mark_btn.config(state="disabled")
        self.mark_status.config(text="")
        self.open_button.config(state="disabled")

    def show_result(self, result):
        self.jobs = result.jobs

        self.all_label.config(text=f"Всего заказов: {result.all_cnt}")
        self.passed_label.config(text=f"Показано: {result.passed_cnt}")
        self.content_filtered_label.config(text="Низкий/без явного контента: -")
        self.stack_filtered_label.config(text=f"Скрыто стеком: {result.exclude_stack_filter_cnt}")

        for index, item in enumerate(result.jobs):
            job = item.job
            tags_text = ", ".join(job.tags[:2]) if job.tags else "-"
            date_text = job.published_at or "-"

            self.tree.insert(
                "", "end", iid=str(index),
                values=(priority_text(item.final_priority), job.title, date_text, item.feed_name, tags_text),
                tags=(priority_tag(item.final_priority),)
            )

        self.status_label.config(text="Готово")
        self.load_button.config(state="normal")

        if result.jobs:
            first_id = self.tree.get_children()[0]
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)
            self.on_job_select(None)

    def on_job_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        item = self.jobs[int(item_id)]
        job = item.job
        analysis = item.basic

        self.selected_job = job
        self.title_var.set(f"Название: {job.title}")
        self.date_var.set(f"Дата: {job.published_at or '-'}")
        self.tags_var.set(f"Теги: {', '.join(job.tags) if job.tags else '-'}")
        self.url_var.set(f"Ссылка: {job.url}")

        self.save_mark_btn.config(state="normal")
        self.mark_status.config(text="")
        self.mark_var.set(item.final_priority.value)
        self.closed_var.set(False)

        self.details_text.delete("1.0", tk.END)

        if hasattr(item, 'ai') and item.ai:
            self.details_text.insert(tk.END, f"Вердикт ИИ: {priority_text(item.ai.priority)}\n")
            self.details_text.insert(tk.END, f"Объяснение ИИ: {item.ai.explanation}\n\n")

        self.details_text.insert(tk.END, f"Базовый приоритет: {priority_text(analysis.priority)}\n")
        self.details_text.insert(tk.END, f"Причина базы: {analysis.reason}\n")
        self.details_text.insert(tk.END, f"RSS-лента: {item.feed_name}\n")

        if analysis.content_keywords:
            self.details_text.insert(tk.END, f"Ключевые слова: {', '.join(analysis.content_keywords)}\n")

        if analysis.excluded_stack:
            self.details_text.insert(tk.END, f"Найден чужой стек: {analysis.excluded_stack}\n")

        self.details_text.insert(tk.END, "\n")

        # Подставь сюда свою функцию present_job
        # self.details_text.insert(tk.END, present_job(job))

        self.open_button.config(state="normal")

    def save_human_mark(self):
        """Сбор данных с панели и отправка в бэкенд с пробросом контекста (item_id)"""
        if not self.selected_job:
            return

        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        mark_value = self.mark_var.get()
        is_closed = self.closed_var.get()

        if mark_value == -1:
            return

        self.save_mark_btn.config(state="disabled")
        self.mark_status.config(text="Сохранение...", foreground="black")

        # Передаем callback через lambda, чтобы "запомнить" над какой строкой мы работаем
        self.backend.human_priority(
            external_id=self.selected_job.external_id,
            mark=mark_value,
            is_closed=is_closed,
            callback=lambda res: self.on_mark_saved(res, item_id, mark_value, is_closed)
        )

    def on_mark_saved(self, result, item_id, mark_value, is_closed):
        current_selected = self.tree.selection()
        is_currently_selected = current_selected and current_selected[0] == item_id

        if isinstance(result, Exception):
            if is_currently_selected:
                self.save_mark_btn.config(state="normal")
                self.mark_status.config(text="Ошибка БД!", foreground="red")
            log.exception(f"Ошибка сохранения разметки: {result}")
            return

        if is_currently_selected:
            self.save_mark_btn.config(state="normal")
            self.mark_status.config(text="✔ Сохранено!", foreground="green")

        if is_closed:
            # Удаляем закрытый заказ из таблицы
            if self.tree.exists(item_id):
                self.tree.delete(item_id)
            # Очищаем правую панель, чтобы не мозолило глаза
            if is_currently_selected:
                self.clear_details_panel()
        else:
            # Обновляем текст в колонке на "✅ HIGH"
            if self.tree.exists(item_id):
                # Создаем временный объект приоритета для функции priority_text
                class TempPriority: value = mark_value

                new_priority_text = priority_text(TempPriority())
                self.tree.set(item_id, "priority", f"✅ {new_priority_text}")

    def open_selected_job(self):
        if self.selected_job and self.selected_job.url:
            webbrowser.open(self.selected_job.url)

    def show_error(self, error: Exception):
        self.status_label.config(text="Ошибка")
        self.load_button.config(state="normal")
        self.open_button.config(state="disabled")
        self.details_text.delete("1.0", tk.END)
        self.details_text.insert("1.0", f"Ошибка при загрузке заказов:\n\n{error}")
        log.exception(error)