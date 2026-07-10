import dto
from db import models
from sqlalchemy import inspect


def map_ai_analysis_to_orm(obj: dto.AIAnalysis) -> models.AIAnalysis:
    return models.AIAnalysis(
        job_id=obj.job_id,
        explanation=obj.explanation,
        confidence=obj.confidence,
        priority=obj.priority
    )


def map_ai_analysis_to_dto(obj: models.AIAnalysis) -> dto.AIAnalysis:
    return dto.AIAnalysis(
        job_id=obj.job_id,
        explanation=obj.explanation,
        confidence=obj.confidence,
        priority=dto.JobPriority(obj.priority)
    )


def map_job_static_data_to_orm(obj: dto.JobStaticData) -> models.JobStaticData:
    return models.JobStaticData(
        id=obj.id,
        url=obj.feed_job.url,
        external_id=obj.feed_job.external_id,
        title=obj.feed_job.title,
        description=obj.page_data.description,
        tags_raw=",".join(obj.feed_job.tags) if obj.feed_job.tags else None,
        source=obj.feed_job.source,
        ai_analysis=map_ai_analysis_to_orm(obj.ai) if obj.ai else None,
        feed_name=obj.feed_job.feed_name,
        is_hidden=obj.is_hidden,
        budget=obj.page_data.budget_text,
        is_closed=obj.page_data.is_closed,
        priority=obj.priority
    )


def map_job_static_data_to_dto(obj: models.JobStaticData) -> dto.JobStaticData:
    job = dto.FeedJob(
        title=obj.title,
        source=obj.source,
        external_id=obj.external_id,
        url=obj.url,
        tags=obj.tags_raw.split(",") if obj.tags_raw else [],
        feed_name=obj.feed_name
    )
    ai = None
    if "ai_analysis" not in inspect(obj).unloaded and obj.ai_analysis is not None:
        ai = map_ai_analysis_to_dto(obj.ai_analysis)

    page_data = dto.JobPageData(is_closed=obj.is_closed, budget_text=obj.budget, description=obj.description)

    return dto.JobStaticData(
        id=obj.id,
        feed_job=job,
        priority=dto.JobPriority(obj.priority),
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
registry.register(dto_cls=dto.JobStaticData, orm_model=models.JobStaticData, to_orm=map_job_static_data_to_orm, to_dto=map_job_static_data_to_dto)