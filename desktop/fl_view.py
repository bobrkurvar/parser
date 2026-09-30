import logging
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from fl.dto import ActiveJob, CollectResult


log = logging.getLogger(__name__)


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

    return f"{price_min:,} – {price_max:,} ₽".replace(",", " ")


class FLView(ttk.Frame):
    def __init__(
        self,
        parent,
        backend,
        enqueue_callback,
    ) -> None:
        super().__init__(parent)

        self.backend = backend
        self.enqueue_callback = enqueue_callback

        self.jobs: dict[str, ActiveJob] = {}
        self.selected_job: ActiveJob | None = None
        self.total_cnt = 0

        self.create_widgets()

    def create_widgets(self) -> None:
        top_frame = ttk.Frame(
            self,
            padding=8,
        )
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
        self.refresh_button.pack(
            side="left",
            padx=(8, 0),
        )

        self.open_button = ttk.Button(
            top_frame,
            text="Открыть в браузере",
            command=self.open_selected_job,
            state="disabled",
        )
        self.open_button.pack(
            side="left",
            padx=(8, 0),
        )

        self.status_label = ttk.Label(
            top_frame,
            text="Готово",
        )
        self.status_label.pack(
            side="left",
            padx=(12, 0),
        )

        paned = ttk.Panedwindow(
            self,
            orient=tk.HORIZONTAL,
        )
        paned.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8,
        )

        self.create_jobs_panel(paned)
        self.create_details_panel(paned)

    def create_jobs_panel(
        self,
        paned: ttk.Panedwindow,
    ) -> None:
        left_frame = ttk.Frame(paned)

        paned.add(
            left_frame,
            weight=1,
        )

        ttk.Label(
            left_frame,
            text="Активные заказы",
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        tree_frame = ttk.Frame(left_frame)

        tree_frame.pack(
            fill="both",
            expand=True,
        )

        tree_frame.columnconfigure(
            0,
            weight=1,
        )

        tree_frame.rowconfigure(
            0,
            weight=1,
        )

        columns = (
            "title",
            "feed",
            "responses",
            "budget",
            "tags",
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=25,
        )

        self.tree.tag_configure(
            "ai_rejected",
            foreground="#777777",
        )

        self.tree.heading(
            "title",
            text="Название",
        )

        self.tree.heading(
            "feed",
            text="Лента",
        )

        self.tree.heading(
            "responses",
            text="Отклики",
        )

        self.tree.heading(
            "budget",
            text="Бюджет",
        )

        self.tree.heading(
            "tags",
            text="Теги",
        )

        self.tree.column(
            "title",
            width=430,
            anchor="w",
        )

        self.tree.column(
            "feed",
            width=175,
            anchor="w",
        )

        self.tree.column(
            "responses",
            width=80,
            anchor="center",
        )

        self.tree.column(
            "budget",
            width=160,
            anchor="w",
        )

        self.tree.column(
            "tags",
            width=210,
            anchor="w",
        )

        scroll_y = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        scroll_x = ttk.Scrollbar(
            tree_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scroll_y.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        scroll_x.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.on_job_select,
        )

    def create_details_panel(
        self,
        paned: ttk.Panedwindow,
    ) -> None:
        right_frame = ttk.Frame(paned)

        paned.add(
            right_frame,
            weight=2,
        )

        ttk.Label(
            right_frame,
            text="Детали заказа",
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        info_frame = ttk.Frame(right_frame)

        info_frame.pack(
            fill="x",
            pady=(0, 8),
        )

        self.title_var = tk.StringVar(
            value="Название: ",
        )

        self.feed_var = tk.StringVar(
            value="Лента: ",
        )

        self.published_at_var = tk.StringVar(
            value="Опубликовано: ",
        )

        self.tags_var = tk.StringVar(
            value="Теги: ",
        )

        self.budget_var = tk.StringVar(
            value="Бюджет: ",
        )

        self.responses_var = tk.StringVar(
            value="Отклики: ",
        )

        self.url_var = tk.StringVar(
            value="Ссылка: ",
        )

        ttk.Label(
            info_frame,
            textvariable=self.title_var,
            font=("Segoe UI", 10, "bold"),
            wraplength=700,
        ).pack(
            anchor="w",
            pady=2,
        )

        for variable in (
            self.feed_var,
            self.published_at_var,
            self.tags_var,
            self.budget_var,
            self.responses_var,
        ):
            ttk.Label(
                info_frame,
                textvariable=variable,
                wraplength=700,
            ).pack(
                anchor="w",
                pady=2,
            )

        self.url_label = ttk.Label(
            info_frame,
            textvariable=self.url_var,
            foreground="blue",
            cursor="hand2",
        )

        self.url_label.pack(
            anchor="w",
            pady=2,
        )

        self.url_label.bind(
            "<Button-1>",
            lambda _event: self.open_selected_job(),
        )

        action_frame = ttk.Frame(right_frame)

        action_frame.pack(
            fill="x",
            pady=(8, 8),
        )

        self.match_button = ttk.Button(
            action_frame,
            text="Подходит",
            command=lambda: self.mark_match(True),
            state="disabled",
        )
        self.match_button.pack(side="left")

        self.responded_button = ttk.Button(
            action_frame,
            text="Откликнулся",
            command=self.mark_responded,
            state="disabled",
        )
        self.responded_button.pack(
            side="left",
            padx=(8, 0),
        )

        self.not_match_button = ttk.Button(
            action_frame,
            text="Не подходит",
            command=lambda: self.mark_match(False),
            state="disabled",
        )
        self.not_match_button.pack(
            side="left",
            padx=(8, 0),
        )


        self.mark_status = ttk.Label(
            action_frame,
            text="",
            font=("Segoe UI", 9, "bold"),
        )

        self.mark_status.pack(
            side="left",
            padx=10,
        )

        ttk.Label(
            right_frame,
            text="Описание",
        ).pack(
            anchor="w",
            pady=(6, 4),
        )

        self.details_text = ScrolledText(
            right_frame,
            wrap="word",
            font=("Consolas", 10),
        )

        self.details_text.pack(
            fill="both",
            expand=True,
        )

    def start_loading(self) -> None:
        self.set_loading_state(
            "Поиск новых и обновление активных заказов...",
        )

        self.clear_ui()

        self.backend.load_jobs(
            callback=lambda result:
                self.enqueue_callback(
                    self.on_loading_complete,
                    result,
                ),
        )

    def start_refresh_active_jobs(self) -> None:
        self.set_loading_state(
            "Обновление активных заказов...",
        )

        self.clear_ui()

        self.backend.refresh_active_jobs(
            callback=lambda result:
                self.enqueue_callback(
                    self.on_loading_complete,
                    result,
                ),
        )

    def set_loading_state(
        self,
        text: str,
    ) -> None:
        self.load_button.config(
            state="disabled",
        )

        self.refresh_button.config(
            state="disabled",
        )

        self.open_button.config(
            state="disabled",
        )

        self.match_button.config(
            state="disabled",
        )

        self.not_match_button.config(
            state="disabled",
        )

        self.status_label.config(
            text=text,
        )

    def on_loading_complete(
        self,
        result,
    ) -> None:
        if isinstance(result, Exception):
            self.show_error(result)
            return

        self.show_result(result)

    def clear_ui(self) -> None:
        self.jobs.clear()

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        self.total_cnt = 0

        self.clear_details_panel()

    def clear_details_panel(self) -> None:
        self.selected_job = None

        self.title_var.set(
            "Название: ",
        )

        self.feed_var.set(
            "Лента: ",
        )

        self.published_at_var.set(
            "Опубликовано: ",
        )

        self.tags_var.set(
            "Теги: ",
        )

        self.budget_var.set(
            "Бюджет: ",
        )

        self.responses_var.set(
            "Отклики: ",
        )

        self.url_var.set(
            "Ссылка: ",
        )

        self.details_text.delete(
            "1.0",
            tk.END,
        )

        self.open_button.config(
            state="disabled",
        )

        self.match_button.config(
            state="disabled",
        )

        self.not_match_button.config(
            state="disabled",
        )

        self.mark_status.config(
            text="",
        )

    def show_result(
        self,
        result: CollectResult,
    ) -> None:
        self.total_cnt = result.total_cnt

        for active_job in result.jobs:
            static_data = active_job.static_data
            job = static_data.feed_job
            page = static_data.page_data
            offer_range = active_job.dynamic_data

            if static_data.id is None:
                log.warning(
                    "Пропущен заказ без ID: external_id=%s",
                    job.external_id,
                )
                continue

            item_id = str(static_data.id)

            self.jobs[item_id] = active_job

            tags_text = (
                ", ".join(job.tags[:2])
                if job.tags
                else "-"
            )

            responses_text = (
                str(offer_range.responses_count)
                if offer_range.responses_count is not None
                else "-"
            )

            budget_text = (
                page.budget_text or "-"
            )

            is_ai_rejected = (
                static_data.matches_profile is None
                and static_data.ai is not None
                and not static_data.ai.matches_profile
            )

            title = (
                f"[AI−] {job.title}"
                if is_ai_rejected
                else job.title
            )

            row_tags = (
                ("ai_rejected",)
                if is_ai_rejected
                else ()
            )

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    title,
                    job.feed_name,
                    responses_text,
                    budget_text,
                    tags_text,
                ),
                tags=row_tags,
            )

        self.update_status()

        self.load_button.config(
            state="normal",
        )

        self.refresh_button.config(
            state="normal",
        )

        children = self.tree.get_children()

        if not children:
            return

        first_id = children[0]

        self.tree.selection_set(
            first_id,
        )

        self.tree.focus(
            first_id,
        )

        self.on_job_select(None)

    def on_responded(
        self,
        result,
        item_id: str,
    ) -> None:
        active_job = self.jobs.get(item_id)
        is_selected = item_id in self.tree.selection()

        if isinstance(result, Exception):
            if is_selected and active_job is not None:
                self.responded_button.config(state="normal")
                self.not_match_button.config(state="normal")

                self.match_button.config(
                    state=(
                        "disabled"
                        if active_job.static_data.matches_profile is True
                        else "normal"
                    ),
                )

                self.mark_status.config(
                    text="Ошибка БД",
                    foreground="red",
                )

            log.error(
                "Ошибка сохранения отклика: %s",
                result,
                exc_info=result,
            )
            return

        self.jobs.pop(item_id, None)

        if self.tree.exists(item_id):
            self.tree.delete(item_id)

        self.update_status()

        if is_selected:
            self.clear_details_panel()
            self.select_first_job()


    def mark_responded(self) -> None:
        if self.selected_job is None:
            return

        static_data = self.selected_job.static_data

        if static_data.id is None:
            self.mark_status.config(
                text="Ошибка: нет ID записи",
                foreground="red",
            )
            return

        item_id = str(static_data.id)

        self.match_button.config(state="disabled")
        self.responded_button.config(state="disabled")
        self.not_match_button.config(state="disabled")

        self.mark_status.config(
            text="Сохранение...",
            foreground="black",
        )

        self.backend.responded(
            job=static_data,
            callback=lambda result: self.enqueue_callback(
                self.on_responded,
                result,
                item_id,
            ),
        )


    def update_status(self) -> None:
        self.status_label.config(
            text=(
                "Готово. "
                f"Актуальных: {len(self.jobs)}; "
                f"всего собрано: {self.total_cnt}"
            ),
        )

    def on_job_select(
        self,
        _event,
    ) -> None:
        selected = self.tree.selection()

        if not selected:
            return

        item_id = selected[0]

        active_job = self.jobs.get(item_id)

        if active_job is None:
            return

        static_data = active_job.static_data
        job = static_data.feed_job
        page = static_data.page_data
        offer_range = active_job.dynamic_data
        ai = static_data.ai

        self.selected_job = active_job

        self.title_var.set(
            f"Название: {job.title}",
        )

        self.feed_var.set(
            f"Лента: {job.feed_name}",
        )

        if isinstance(
            job.published_at,
            datetime,
        ):
            published_at_text = (
                job.published_at.strftime(
                    "%d.%m.%Y %H:%M",
                )
            )
        else:
            published_at_text = (
                job.published_at or "-"
            )

        self.published_at_var.set(
            f"Опубликовано: {published_at_text}",
        )

        self.tags_var.set(
            "Теги: "
            + (
                ", ".join(job.tags)
                if job.tags
                else "-"
            ),
        )

        self.budget_var.set(
            f"Бюджет: {page.budget_text or '-'}",
        )

        self.url_var.set(
            f"Ссылка: {job.url}",
        )

        responses_count = (
            offer_range.responses_count
            if offer_range.responses_count is not None
            else "-"
        )

        price_range = format_price_range(
            offer_range.response_price_min,
            offer_range.response_price_max,
        )

        self.responses_var.set(
            "Отклики: "
            f"{responses_count}; "
            f"цены: {price_range}",
        )

        self.details_text.delete(
            "1.0",
            tk.END,
        )

        if ai is not None:
            ai_status = (
                "Подходит"
                if ai.matches_profile
                else "Предварительно не подходит"
            )

            self.details_text.insert(
                tk.END,
                f"ИИ: {ai_status}\n",
            )

            self.details_text.insert(
                tk.END,
                "Объяснение ИИ: "
                f"{ai.explanation or '-'}"
                "\n\n",
            )

        self.details_text.insert(
            tk.END,
            page.description,
        )

        self.open_button.config(
            state="normal",
        )

        self.match_button.config(
            state=(
                "disabled"
                if static_data.matches_profile is True
                else "normal"
            ),
        )

        self.not_match_button.config(
            state="normal",
        )
        self.responded_button.config(state="normal")

        self.mark_status.config(
            text=(
                "Подходит"
                if static_data.matches_profile is True
                else ""
            ),
        )

    def mark_match(self, matches_profile: bool) -> None:
        if self.selected_job is None:
            return

        static_data = self.selected_job.static_data

        if static_data.id is None:
            self.mark_status.config(
                text="Ошибка: нет ID записи",
                foreground="red",
            )
            return

        item_id = str(static_data.id)

        self.match_button.config(state="disabled")
        self.not_match_button.config(state="disabled")

        self.mark_status.config(
            text="Сохранение...",
            foreground="black",
        )

        self.backend.update_match(
            #job_id=static_data.id,
            job=static_data,
            matches_profile=matches_profile,
            callback=lambda result: self.enqueue_callback(
                self.on_match_updated,
                result,
                item_id,
                matches_profile,
            ),
        )

    def on_match_updated(
        self,
        result,
        item_id: str,
        matches_profile: bool,
    ) -> None:
        active_job = self.jobs.get(item_id)
        is_selected = item_id in self.tree.selection()

        if isinstance(result, Exception):
            if is_selected and active_job is not None:
                self.match_button.config(
                    state=(
                        "disabled"
                        if active_job.static_data.matches_profile is True
                        else "normal"
                    ),
                )
                self.not_match_button.config(
                    state="normal",
                )

                self.mark_status.config(
                    text="Ошибка БД",
                    foreground="red",
                )

            log.error(
                "Ошибка сохранения matches_profile: %s",
                result,
                exc_info=result,
            )
            return

        if active_job is None:
            return

        active_job.static_data.matches_profile = matches_profile

        if not matches_profile:
            self.jobs.pop(item_id, None)

            if self.tree.exists(item_id):
                self.tree.delete(item_id)

            self.update_status()

            if is_selected:
                self.clear_details_panel()
                self.select_first_job()

            return

        if self.tree.exists(item_id):
            self.tree.set(
                item_id,
                "title",
                active_job.static_data.feed_job.title,
            )
            self.tree.item(
                item_id,
                tags=(),
            )

        if is_selected:
            self.match_button.config(
                state="disabled",
            )
            self.not_match_button.config(
                state="normal",
            )
            self.mark_status.config(
                text="Подходит",
                foreground="black",
            )

    def select_first_job(self) -> None:
        children = self.tree.get_children()

        if not children:
            return

        first_id = children[0]

        self.tree.selection_set(
            first_id,
        )

        self.tree.focus(
            first_id,
        )

        self.on_job_select(None)

    def open_selected_job(self) -> None:
        if self.selected_job is None:
            return

        url = (
            self.selected_job
            .static_data
            .feed_job
            .url
        )

        if url:
            webbrowser.open(url)

    def show_error(
        self,
        error: Exception,
    ) -> None:
        self.status_label.config(
            text="Ошибка",
        )

        self.load_button.config(
            state="normal",
        )

        self.refresh_button.config(
            state="normal",
        )

        self.open_button.config(
            state="disabled",
        )

        self.match_button.config(
            state="disabled",
        )

        self.not_match_button.config(
            state="disabled",
        )

        self.details_text.delete(
            "1.0",
            tk.END,
        )

        self.details_text.insert(
            "1.0",
            "Ошибка при загрузке заказов:\n\n"
            f"{error}",
        )

        log.error(
            "Ошибка загрузки: %s",
            error,
            exc_info=error,
        )