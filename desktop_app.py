import tkinter as tk
import webbrowser

from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.logger import setup_logging
from present import present_job

from dto import JobPriority
import logging


log = logging.getLogger(__name__)

def priority_text(priority: JobPriority) -> str | None:
    if priority == JobPriority.HIGH:
        return "🔥 HIGH"
    if priority == JobPriority.MEDIUM:
        return "⚠️ MEDIUM"
    if priority == JobPriority.LOW:
        return "LOW"

def priority_tag(priority: JobPriority) -> str:
    if priority == JobPriority.HIGH:
        return "high"
    if priority == JobPriority.MEDIUM:
        return "medium"
    if priority == JobPriority.LOW:
        return "low"
    return "hidden"

class App(tk.Tk):
    def __init__(self, backend):
        super().__init__()

        self.title("Freelance Parser")
        self.geometry("1400x800")

        self.jobs = []
        self.selected_job = None

        self.create_widgets()
        self.backend = backend

    def create_widgets(self):
        # =========================
        # Верхняя панель
        # =========================
        top_frame = ttk.Frame(self, padding=8)
        top_frame.pack(fill="x")

        self.load_button = ttk.Button(
            top_frame,
            text="Загрузить заказы",
            command=self.start_loading
        )
        self.load_button.pack(side="left")

        self.open_button = ttk.Button(
            top_frame,
            text="Открыть в браузере",
            command=self.open_selected_job,
            state="disabled"
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

        self.content_filtered_label = ttk.Label(
            stats_frame,
            text="Отфильтровано контентом: 0"
        )
        self.content_filtered_label.pack(side="left", padx=(0, 20))

        self.stack_filtered_label = ttk.Label(
            stats_frame,
            text="Отфильтровано стеком: 0"
        )
        self.stack_filtered_label.pack(side="left", padx=(0, 20))

        # =========================
        # Основная область
        # =========================
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        # Левая панель — список заказов
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Список заказов").pack(anchor="w", pady=(0, 6))

        columns = ("priority", "title", "date", "feed", "tags")
        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="headings",
            height=25
        )
        self.tree.tag_configure("high", background="#fff2cc")
        self.tree.tag_configure("medium", background="#e8f4ff")
        self.tree.tag_configure("low", background="#f2f2f2")

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

        # Правая панель — детали
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Детали заказа").pack(anchor="w", pady=(0, 6))

        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill="x", pady=(0, 8))

        self.title_var = tk.StringVar(value="Название: ")
        self.date_var = tk.StringVar(value="Дата: ")
        self.tags_var = tk.StringVar(value="Теги: ")
        self.url_var = tk.StringVar(value="Ссылка: ")

        ttk.Label(info_frame, textvariable=self.title_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.date_var).pack(anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.tags_var).pack(anchor="w", pady=2)
        ttk.Label(info_frame, textvariable=self.url_var, foreground="blue").pack(anchor="w", pady=2)

        ttk.Label(right_frame, text="Описание").pack(anchor="w", pady=(6, 4))

        self.details_text = ScrolledText(
            right_frame,
            wrap="word",
            font=("Consolas", 10)
        )
        self.details_text.pack(fill="both", expand=True)


    def start_loading(self):
        self.load_button.config(state="disabled")
        self.open_button.config(state="disabled")
        self.status_label.config(text="Загрузка...")

        self.clear_ui()

        self.backend.collect_and_save(self.on_loading_complete)

    def on_loading_complete(self, result):
        """Callback, который вызывается, когда асинхронный поток закончил работу"""
        if isinstance(result, Exception):
            self.show_error(result)
        else:
            self.show_result(result)


    def clear_ui(self):
        self.jobs = []
        self.selected_job = None

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.details_text.delete("1.0", tk.END)

        self.title_var.set("Название: ")
        self.date_var.set("Дата: ")
        self.tags_var.set("Теги: ")
        self.url_var.set("Ссылка: ")

    def show_result(self, result):
        self.jobs = result.jobs

        self.all_label.config(text=f"Всего заказов: {result.all_cnt}")
        self.passed_label.config(text=f"Показано: {result.passed_cnt}")
        self.content_filtered_label.config(
            text=f"Низкий/без явного контента: -"
        )
        self.stack_filtered_label.config(
            text=f"Скрыто стеком: {result.exclude_stack_filter_cnt}"
        )

        for index, item in enumerate(result.jobs):
            job = item.job
            #analysis = item.basic

            tags_text = ", ".join(job.tags[:2]) if job.tags else "-"
            date_text = job.published_at or "-"

            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    priority_text(item.final_priority),
                    job.title,
                    date_text,
                    item.feed_name,
                    tags_text,
                ),
                tags=(priority_tag(item.final_priority),),
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

        self.details_text.delete("1.0", tk.END)

        self.details_text.insert(tk.END, f"Приоритет: {priority_text(analysis.priority)}\n")
        self.details_text.insert(tk.END, f"Причина: {analysis.reason}\n")
        self.details_text.insert(tk.END, f"RSS-лента: {item.feed_name}\n")

        if analysis.content_keywords:
            self.details_text.insert(
                tk.END,
                f"Ключевые слова: {', '.join(analysis.content_keywords)}\n"
            )

        if analysis.excluded_stack:
            self.details_text.insert(
                tk.END,
                f"Найден чужой стек: {analysis.excluded_stack}\n"
            )

        self.details_text.insert(tk.END, "\n")
        self.details_text.insert(tk.END, present_job(job))

        self.open_button.config(state="normal")

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

