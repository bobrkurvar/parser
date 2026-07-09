import dto
from db import models
from sqlalchemy import inspect

from dto import JobPriority, PageData


def map_ai_analysis_to_orm(obj: dto.AIAnalysis):
    return models.AIAnalysis(
        job_id=obj.job_id,
        explanation=obj.explanation,
        confidence=obj.confidence,
    )


def map_ai_analysis_to_dto(obj: models.AIAnalysis):
    return dto.AIAnalysis(
        job_id=obj.job_id,
        explanation=obj.explanation,
        confidence=obj.confidence,
    )


def map_job_view_to_orm(obj: dto.JobView):
    return models.JobView(
        id=obj.id,
        url=obj.job.url,
        external_id=obj.job.external_id,
        title=obj.job.title,
        description=obj.job.description,
        tags_raw=",".join(obj.job.tags) if obj.job.tags else None,
        source=obj.job.feed_name,
        ai_analisys=map_ai_analysis_to_orm(obj.ai) if obj.ai else None,
        feed_name=obj.job.feed_name,
        is_hidden=obj.is_hidden
    )


def map_job_view_to_dto(obj: models.JobView):
    job = dto.FeedJob(
        title=obj.title,
        description=obj.description,
        source=obj.source,
        external_id=obj.external_id,
        url=obj.url,
        tags=obj.tags_raw.split(",") if obj.tags_raw else [],
        feed_name=obj.feed_name
    )
    ai = None
    if "ai_analysis" not in inspect(obj).unloaded:
        ai = map_ai_analysis_to_dto(obj.ai_analysis)

    page_data = PageData(is_closed=obj.is_closed, budget_text=obj.budget)

    return dto.JobView(
        id=obj.id,
        job=job,
        priority=JobPriority(obj.priority),
        ai=ai,
        page_data=page_data
    )



class MapperRegistry:
    def __init__(self):
        self._models = {}
        self._to_orm_funcs = {}
        self._to_dto_funcs = {}

    def register(self, dto_cls, orm_model, to_orm, to_dto):
        self._models[dto_cls] = orm_model
        self._to_orm_funcs[dto_cls] = to_orm
        self._to_dto_funcs[orm_model] = to_dto

    def get_model(self, dto_cls):
        return self._models[dto_cls]

    def to_orm(self, dto_obj):
        dto_cls = type(dto_obj)
        func = self._to_orm_funcs.get(dto_cls)
        if not func:
            raise RuntimeError(f"Маппер в ORM не найден для {dto_cls}")
        return func(dto_obj)

    def to_dto(self, orm_obj):
        orm_cls = type(orm_obj)
        func = self._to_dto_funcs.get(orm_cls)
        if not func:
            raise RuntimeError(f"Маппер в Домен не найден для {orm_cls}")
        return func(orm_obj)


registry = MapperRegistry()
registry.register(dto_cls=dto.JobView, orm_model=models.JobView, to_orm=map_job_view_to_orm, to_dto=map_job_view_to_dto)