from dto import FreelanceJob

def present_job(job: FreelanceJob) -> str:
    tags = ", ".join(job.tags) if job.tags else "без тегов"

    description = job.description.strip()

    return (
        f"Источник: {job.source}\n"
        f"Название: {job.title}\n"
        f"Дата: {job.published_at or 'не указана'}\n"
        f"Теги: {tags}\n"
        f"Ссылка: {job.url}\n\n"
        f"Описание:\n{description}"
    )