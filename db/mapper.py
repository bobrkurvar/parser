import dto
from db import models
from dto import JobPriority


def job_view_to_orm(obj: dto.JobView):
    return models.JobView(
        url=obj.job.url,
        external_id=obj.job.external_id,
        title=obj.job.title,
        description=obj.job.description,
        tags_raw=",".join(obj.job.tags) if obj.job.tags else None,
        source=obj.job.feed_name,
        ai_priority=obj.ai.priority.value,
        ai_tech_tags=",".join(obj.ai.tech_tags) if obj.ai.tech_tags else None,
        ai_explanation=obj.ai.explanation,
        ai_confidence=obj.ai.confidence,
    )


def job_view_to_dto(obj: models.JobView):
    job = dto.FreelanceJob(
        title=obj.title,
        description=obj.description,
        source=obj.source,
        external_id=obj.external_id,
        url=obj.url,
        tags=obj.tags_raw.split(",") if obj.tags_raw else [],
        feed_name=obj.feed_name
    )
    ai = dto.AIAnalysis(
        priority=JobPriority(obj.ai_priority),
        confidence=obj.ai_confidence,
        explanation=obj.ai_explanation,
        tech_tags=obj.ai_tech_tags.split(",") if obj.ai_tech_tags else []
    )
    return dto.JobView(
        job=job,
        human_priority=JobPriority(obj.human_priority),
        ai=ai
    )

#def active_job_view_to_dto(obj: models.ActiveJobs):



class MapperRegistry:
    def __init__(self):
        self._models = {}  # domain_cls -> orm_model
        self._to_orm_funcs = {}  # domain_cls -> func
        self._to_domain_funcs = {}  # orm_model -> func (Внимание: ключ - ORM класс!)

    def register(self, dto_cls, orm_model, to_orm, to_dto):
        self._models[dto_cls] = orm_model
        self._to_orm_funcs[dto_cls] = to_orm
        self._to_domain_funcs[orm_model] = to_dto

    def get_model(self, dto_cls):
        return self._models[dto_cls]

    def to_orm(self, dto_obj):
        dto_cls = type(dto_obj)
        func = self._to_orm_funcs.get(dto_cls)
        if not func:
            raise RuntimeError(f"Маппер в ORM не найден для {dto_cls}")
        return func(dto_obj)

    def from_orm(self, orm_obj):
        orm_cls = type(orm_obj)
        func = self._to_domain_funcs.get(orm_cls)
        if not func:
            raise RuntimeError(f"Маппер в Домен не найден для {orm_cls}")
        return func(orm_obj)


registry = MapperRegistry()
registry.register(dto_cls=dto.JobView, orm_model=models.JobView, to_orm=job_view_to_orm, to_dto=lambda: None)
#registry.register(dto_cls=dto.ActiveJob, orm_model=models.ActiveJobs, to_orm=lambda: None, to_dto=active_job_view_to_dto)