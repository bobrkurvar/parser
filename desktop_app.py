import logging
import tkinter as tk
import webbrowser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from dto import JobPriority, JobView

log = logging.getLogger(__name__)


def priority_text(priority: JobPriority | None) -> str:
    if priority is None:
        return "—"

    if priority == JobPriority.HIGH:
        return "🔥 HIGH"

    if priority == JobPriority.MEDIUM:
        return "⚠️ MEDIUM"

    if priority == JobPriority.LOW:
        return "LOW"

    return "HIDDEN"


def priority_tag(priority: JobPriority | None) -> str:
    if priority == JobPriority.HIGH:
        return "high"

    if priority == JobPriority.MEDIUM:
        return "medium"

    if priority == JobPriority.LOW:
        return "low"

    return "hidden"


def format_price_range(
    price_min: int | None,
    price_max: int | None,
) -> str:
    if price_min is None and price_max is None:
        return "-"

    if price_min == price_max:
        return f"{price_min:,} ₽".replace(",", " ")

    if price_min is None:
        return f"до {price_max:,} ₽".replace(",", " ")

    if price_max is None:
        return f"от {price_min:,} ₽".replace(",", " ")

    return (
        f"{price_min:,} – {price_max:,} ₽"
        .replace(",", " ")
    )


class App(tk.Tk):
    def __init__(self, backend):
        super().__init__()

        self.title("Freelance Parser")
        self.geometry("1450x800")

        self.jobs: list[JobView] = []
        self.selected_job = None
        self.backend = backend

        self.create_widgets()

    def create_widgets(self) -> None:
        top_frame = ttk.Frame(self, padding=8)
        top_frame.pack(fill="x")

        self.load_button = ttk.Button(
            top_frame,
            text="Загрузить и обновить",
            command=self.start_loading,
        )
        self.load_button.pack(side="left")

        self.refresh_button = ttk.Button(
            top_frame,
            text="Обновить активные",
            command=self.start_refresh_active_jobs,
        )
        self.refresh_button.pack(side="left", padx=(8, 0))

        self.open_button = ttk.Button(
            top_frame,
            text="Открыть в браузере",
            command=self.open_selected_job,
            state="disabled",
        )
        self.open_button.pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(
            top_frame,
            text="Готово",
        )
        self.status_label.pack(side="left", padx=(12, 0))

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text="Активные вакансии",
        ).pack(anchor="w", pady=(0, 6))

        columns = (
            "priority",
            "title",
            "feed",
            "responses",
            "budget",
            "tags",
        )

        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="headings",
            height=25,
        )

        self.tree.tag_configure("high", background="#fff2cc")
        self.tree.tag_configure("medium", background="#e8f4ff")
        self.tree.tag_configure("low", background="#f2f2f2")
        self.tree.tag_configure(
            "hidden",
            foreground="#999999",
        )

        self.tree.heading("priority", text="Приоритет")
        self.tree.heading("title", text="Название")
        self.tree.heading("feed", text="Лента")
        self.tree.heading("responses", text="Отклики")
        self.tree.heading("budget", text="Бюджет")
        self.tree.heading("tags", text="Теги")

        self.tree.column("priority", width=105, anchor="center")
        self.tree.column("title", width=370, anchor="w")
        self.tree.column("feed", width=175, anchor="w")
        self.tree.column("responses", width=80, anchor="center")
        self.tree.column("budget", width=160, anchor="w")
        self.tree.column("tags", width=210, anchor="w")

        tree_scroll_y = ttk.Scrollbar(
            left_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        tree_scroll_x = ttk.Scrollbar(
            left_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
        )

        self.tree.pack(
            fill="both",
            expand=True,
            side="left",
        )
        tree_scroll_y.pack(fill="y", side="right")
        tree_scroll_x.pack(fill="x", side="bottom")

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.on_job_select,
        )

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(
            right_frame,
            text="Детали вакансии",
        ).pack(anchor="w", pady=(0, 6))

        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill="x", pady=(0, 8))

        self.title_var = tk.StringVar(value="Название: ")
        self.feed_var = tk.StringVar(value="Лента: ")
        self.tags_var = tk.StringVar(value="Теги: ")
        self.budget_var = tk.StringVar(value="Бюджет: ")
        self.responses_var = tk.StringVar(value="Отклики: ")
        self.url_var = tk.StringVar(value="Ссылка: ")

        ttk.Label(
            info_frame,
            textvariable=self.title_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=700,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.feed_var,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.tags_var,
            wraplength=700,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.budget_var,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.responses_var,
        ).pack(anchor="w", pady=2)

        ttk.Label(
            info_frame,
            textvariable=self.url_var,
            foreground="blue",
            cursor="hand2",
        ).pack(anchor="w", pady=2)

        self.mark_frame = ttk.LabelFrame(
            right_frame,
            text="Разметка для обучения",
        )
        self.mark_frame.pack(fill="x", pady=(8, 8), padx=4)

        self.mark_var = tk.IntVar(value=-1)

        rb_frame = ttk.Frame(self.mark_frame)
        rb_frame.pack(
            anchor="w",
            fill="x",
            padx=5,
            pady=4,
        )

        ttk.Radiobutton(
            rb_frame,
            text="HIDDEN (0)",
            variable=self.mark_var,
            value=JobPriority.HIDDEN.value,
        ).pack(side="left", padx=(0, 10))

        ttk.Radiobutton(
            rb_frame,
            text="LOW (1)",
            variable=self.mark_var,
            value=JobPriority.LOW.value,
        ).pack(side="left", padx=10)

        ttk.Radiobutton(
            rb_frame,
            text="MEDIUM (2)",
            variable=self.mark_var,
            value=JobPriority.MEDIUM.value,
        ).pack(side="left", padx=10)

        ttk.Radiobutton(
            rb_frame,
            text="HIGH (3)",
            variable=self.mark_var,
            value=JobPriority.HIGH.value,
        ).pack(side="left", padx=10)

        button_frame = ttk.Frame(self.mark_frame)
        button_frame.pack(
            anchor="w",
            fill="x",
            padx=5,
            pady=(0, 6),
        )

        self.save_mark_btn = ttk.Button(
            button_frame,
            text="Сохранить оценку",
            command=self.save_human_mark,
            state="disabled",
        )
        self.save_mark_btn.pack(side="left")

        self.mark_status = ttk.Label(
            button_frame,
            text="",
            font=("Segoe UI", 9, "bold"),
        )
        self.mark_status.pack(side="left", padx=10)

        ttk.Label(
            right_frame,
            text="Описание",
        ).pack(anchor="w", pady=(6, 4))

        self.details_text = ScrolledText(
            right_frame,
            wrap="word",
            font=("Consolas", 10),
        )
        self.details_text.pack(fill="both", expand=True)

    def start_loading(self) -> None:
        self.load_button.config(state="disabled")
        self.refresh_button.config(state="disabled")
        self.open_button.config(state="disabled")

        self.status_label.config(
            text="Поиск новых и обновление активных вакансий...",
        )

        self.clear_ui()

        self.backend.load_jobs(
            self.on_loading_complete,
        )

    def start_refresh_active_jobs(self) -> None:
        self.load_button.config(state="disabled")
        self.refresh_button.config(state="disabled")
        self.open_button.config(state="disabled")

        self.status_label.config(
            text="Обновление активных вакансий...",
        )

        self.clear_ui()

        self.backend.refresh_active_jobs(
            self.on_loading_complete,
        )

    def on_loading_complete(self, result) -> None:
        if isinstance(result, Exception):
            self.show_error(result)
            return

        self.show_result(result)

    def clear_ui(self) -> None:
        self.jobs = []

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        self.clear_details_panel()

    def clear_details_panel(self) -> None:
        self.selected_job = None

        self.title_var.set("Название: ")
        self.feed_var.set("Лента: ")
        self.tags_var.set("Теги: ")
        self.budget_var.set("Бюджет: ")
        self.responses_var.set("Отклики: ")
        self.url_var.set("Ссылка: ")

        self.details_text.delete("1.0", tk.END)

        self.mark_var.set(-1)
        self.save_mark_btn.config(state="disabled")
        self.mark_status.config(text="")
        self.open_button.config(state="disabled")

    def show_result(self, jobs: list[JobView]) -> None:
        self.jobs = jobs

        # self.active_jobs_label.config(
        #     text=f"Активных вакансий: {len(jobs)}",
        # )

        for index, job_view in enumerate(jobs):
            job = job_view.job
            page = job_view.page_data

            priority = job_view.final_priority

            tags_text = (
                ", ".join(job.tags[:2])
                if job.tags
                else "-"
            )

            responses_text = (
                str(page.offer_range.responses_count)
                if page is not None
                    and page.offer_range.responses_count is not None
                else "-"
            )

            budget_text = (
                page.page_data.budget_text
                if page is not None
                   and page.page_data.budget_text
                else "-"
            )

            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    priority_text(priority),
                    job.title,
                    job.feed_name,
                    responses_text,
                    budget_text,
                    tags_text,
                ),
                tags=(priority_tag(priority),),
            )

        self.status_label.config(
            text=f"Готово. Актуальных вакансий: {len(jobs)}",
        )
        self.load_button.config(state="normal")
        self.refresh_button.config(state="normal")

        if not jobs:
            return

        first_id = self.tree.get_children()[0]

        self.tree.selection_set(first_id)
        self.tree.focus(first_id)
        self.on_job_select(None)

    def on_job_select(self, event) -> None:
        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        job_view = self.jobs[int(item_id)]

        job = job_view.job
        ai = job_view.ai
        page = job_view.page_data
        priority = job_view.final_priority

        self.selected_job = job

        self.title_var.set(f"Название: {job.title}")
        self.feed_var.set(f"Лента: {job.feed_name}")
        self.tags_var.set(
            f"Теги: {', '.join(job.tags) if job.tags else '-'}",
        )
        self.budget_var.set(
            f"Бюджет: {job.budget_text or '-'}",
        )
        self.url_var.set(f"Ссылка: {job.url}")

        if page is None:
            self.responses_var.set("Отклики: данные не получены")
        else:
            responses_count = (
                page.offer_range.responses_count
                if page.offer_range.responses_count is not None
                else "-"
            )

            price_range = format_price_range(
                page.offer_range.response_price_min,
                page.offer_range.response_price_max,
            )

            self.responses_var.set(
                f"Отклики: {responses_count}; "
                f"цены: {price_range}",
            )

        self.mark_var.set(
            priority.value
            if priority is not None
            else -1,
        )

        self.save_mark_btn.config(state="normal")
        self.mark_status.config(text="")

        self.details_text.delete("1.0", tk.END)

        if ai is not None:
            self.details_text.insert(
                tk.END,
                f"Вердикт ИИ: {priority_text(ai.priority)}\n",
            )
            self.details_text.insert(
                tk.END,
                f"Объяснение ИИ: {ai.explanation or '-'}\n",
            )

        self.details_text.insert(
            tk.END,
            f"{job.description}",
        )

        self.open_button.config(state="normal")

    def save_human_mark(self) -> None:
        if self.selected_job is None:
            return

        selected = self.tree.selection()
        if not selected:
            return

        mark_value = self.mark_var.get()
        if mark_value == -1:
            return

        item_id = selected[0]

        self.save_mark_btn.config(state="disabled")
        self.mark_status.config(
            text="Сохранение...",
            foreground="black",
        )

        self.backend.human_priority(
            external_id=self.selected_job.external_id,
            mark=mark_value,
            callback=lambda result: self.on_mark_saved(
                result=result,
                item_id=item_id,
                mark_value=mark_value,
            ),
        )

    def on_mark_saved(
        self,
        result,
        item_id: str,
        mark_value: int,
    ) -> None:
        if isinstance(result, Exception):
            self.save_mark_btn.config(state="normal")
            self.mark_status.config(
                text="Ошибка БД",
                foreground="red",
            )
            log.exception(
                "Ошибка сохранения разметки: %s",
                result,
            )
            return

        job_view = self.jobs[int(item_id)]
        job_view.human_priority = JobPriority(mark_value)

        self.tree.set(
            item_id,
            "priority",
            priority_text(job_view.final_priority),
        )

        self.tree.item(
            item_id,
            tags=(priority_tag(job_view.final_priority),),
        )

        self.save_mark_btn.config(state="normal")
        self.mark_status.config(
            text="Сохранено",
            foreground="green",
        )

    def open_selected_job(self) -> None:
        if self.selected_job is None:
            return

        if self.selected_job.url:
            webbrowser.open(self.selected_job.url)

    def show_error(self, error: Exception) -> None:
        self.status_label.config(text="Ошибка")
        self.load_button.config(state="normal")
        self.refresh_button.config(state="normal")
        self.open_button.config(state="disabled")

        self.details_text.delete("1.0", tk.END)
        self.details_text.insert(
            "1.0",
            f"Ошибка при загрузке вакансий:\n\n{error}",
        )

        log.exception("Ошибка загрузки: %s", error)