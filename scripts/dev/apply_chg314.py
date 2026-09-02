"""一次性应用 CHG-20260903-frontend-fullstack-reliability 的精确源码补丁。

该脚本只服务当前开发分支；完成 Contract/generated client 生成并验证后必须删除。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, got {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_in_section(path: str, start: str, end: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    section = text[start_index:end_index]
    count = section.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: section expected one anchor, got {count}: {old!r}")
    section = section.replace(old, new, 1)
    target.write_text(text[:start_index] + section + text[end_index:], encoding="utf-8")


def patch_keyword_contract() -> None:
    path = "backend/src/aima_ugc/contracts/http.py"
    old = '''class KeywordPackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Keyword Pack 名称不能为空")
        return value


class KeywordPackKeywordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    priority: int = 100
    enabled: bool = True
    note: str = Field(default="", max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("关键词不能为空")
        return value
'''
    new = '''class KeywordPackKeywordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    priority: int = 100
    enabled: bool = True
    note: str = Field(default="", max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("关键词不能为空")
        return value


class KeywordPackCreateRequest(BaseModel):
    """创建词包；可在同一事务中携带初始关键词，旧客户端仍可省略。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    keywords: tuple[KeywordPackKeywordCreateRequest, ...] = Field(default=(), max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Keyword Pack 名称不能为空")
        return value
'''
    replace_once(path, old, new)


def patch_keyword_service() -> None:
    path = "backend/src/aima_ugc/bootstrap/import_http.py"
    old = '''            with session.begin():
                pack = PostgresKeywordCatalogRepository(session).create_pack(
                    KeywordPack(
                        id=uuid4(),
                        name=name,
                        description=request.description.strip(),
                        enabled=True,
                        version=1,
                    )
                )
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="keyword_pack_created",
                    object_type="keyword_pack",
                    object_id=str(pack.id),
                    detail={"version": pack.version, "enabled": pack.enabled},
                )
                return _pack_response(PostgresKeywordCatalogRepository(session), pack)
'''
    new = '''            with session.begin():
                repository = PostgresKeywordCatalogRepository(session)
                pack = repository.create_pack(
                    KeywordPack(
                        id=uuid4(),
                        name=name,
                        description=request.description.strip(),
                        enabled=True,
                        version=1,
                    )
                )
                for keyword_request in request.keywords:
                    text = keyword_request.text.strip()
                    try:
                        normalized = normalize_keyword_storage_text(text)
                    except ValueError as exc:
                        raise ValueError("关键词不能为空") from exc
                    keyword = repository.get_or_create_keyword(
                        Keyword(
                            id=uuid4(),
                            text=text,
                            normalized_text=normalized,
                            enabled=True,
                        )
                    )
                    repository.add_item_if_missing(
                        KeywordPackItem(
                            pack_id=pack.id,
                            keyword_id=keyword.id,
                            platform_scope="all",
                            priority=keyword_request.priority,
                            enabled=keyword_request.enabled,
                            note=keyword_request.note.strip(),
                        )
                    )
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="keyword_pack_created",
                    object_type="keyword_pack",
                    object_id=str(pack.id),
                    detail={
                        "version": pack.version,
                        "enabled": pack.enabled,
                        "initial_keyword_count": len(request.keywords),
                    },
                )
                return _pack_response(repository, pack)
'''
    replace_once(path, old, new)


def patch_audit_contract() -> None:
    path = "backend/src/aima_ugc/contracts/administration.py"
    old = '''class AuditEventResponse(BaseModel):
    """安全审计事件投影。"""
'''
    new = '''class AuditEventListQuery(BaseModel):
    """管理员审计事件稳定 Offset 分页。"""

    model_config = ConfigDict(extra="forbid")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)


class AuditEventResponse(BaseModel):
    """安全审计事件投影。"""
'''
    replace_once(path, old, new)
    replace_once(
        path,
        '''class AuditEventListResponse(BaseModel):
    """管理员最近审计事件列表。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[AuditEventResponse, ...]
''',
        '''class AuditEventListResponse(BaseModel):
    """管理员审计事件分页响应。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[AuditEventResponse, ...]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
''',
    )
    replace_once(path, '    "AuditEventListResponse",\n', '    "AuditEventListQuery",\n    "AuditEventListResponse",\n')


def patch_audit_repository_and_service() -> None:
    path = "backend/src/aima_ugc/adapters/persistence/postgres/system.py"
    replace_once(
        path,
        '''    def list_recent(self, *, limit: int) -> tuple[AuditEvent, ...]:
        """按时间倒序返回有界审计事件，不提供任意正文搜索。"""

        rows = self._session.execute(
            select(audit_events_table)
            .order_by(audit_events_table.c.created_at.desc(), audit_events_table.c.id.desc())
            .limit(limit)
        ).mappings()
        return tuple(
''',
        '''    def list_page(self, *, offset: int, limit: int) -> tuple[AuditEvent, ...]:
        """按时间倒序分页读取审计事件，不提供任意正文搜索。"""

        rows = self._session.execute(
            select(audit_events_table)
            .order_by(audit_events_table.c.created_at.desc(), audit_events_table.c.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
        return tuple(
''',
    )
    replace_once(
        path,
        '''            for row in rows
        )
''',
        '''            for row in rows
        )

    def list_recent(self, *, limit: int) -> tuple[AuditEvent, ...]:
        """兼容旧内部调用，等价于读取第一页。"""

        return self.list_page(offset=0, limit=limit)

    def count(self) -> int:
        """返回完整审计事件数量，供稳定分页使用。"""

        return int(self._session.scalar(select(func.count()).select_from(audit_events_table)) or 0)
''',
    )

    path = "backend/src/aima_ugc/bootstrap/administration_http.py"
    replace_once(
        path,
        '''    def list_audit_events(self, *, limit: int) -> AuditEventListResponse:
        """管理员读取最近审计记录。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                events = PostgresAuditRepository(session).list_recent(limit=limit)
                return AuditEventListResponse(
                    items=tuple(
                        AuditEventResponse(
                            id=event.id,
                            actor_ref=event.actor_ref,
                            event_type=event.event_type,
                            object_type=event.object_type,
                            object_id=event.object_id,
                            request_id=event.request_id,
                            safe_detail=cast(dict[str, object], event.safe_detail),
                            created_at=event.created_at,
                        )
                        for event in events
                    )
                )
        finally:
            session.close()
''',
        '''    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        """管理员分页读取完整审计历史。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAuditRepository(session)
                events = repository.list_page(offset=offset, limit=limit)
                return AuditEventListResponse(
                    items=tuple(
                        AuditEventResponse(
                            id=event.id,
                            actor_ref=event.actor_ref,
                            event_type=event.event_type,
                            object_type=event.object_type,
                            object_id=event.object_id,
                            request_id=event.request_id,
                            safe_detail=cast(dict[str, object], event.safe_detail),
                            created_at=event.created_at,
                        )
                        for event in events
                    ),
                    total=repository.count(),
                    offset=offset,
                    limit=limit,
                )
        finally:
            session.close()
''',
    )

    path = "backend/src/aima_ugc/modules/administration/http.py"
    replace_once(
        path,
        '''    def list_audit_events(self, *, limit: int) -> AuditEventListResponse:
        """读取最近管理员安全审计摘要。"""

        ...
''',
        '''    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        """分页读取管理员安全审计摘要。"""

        ...
''',
    )


def patch_audit_route() -> None:
    path = "backend/src/aima_ugc/bootstrap/api.py"
    replace_once(path, '    AuditEventListResponse,\n', '    AuditEventListQuery,\n    AuditEventListResponse,\n')
    replace_once(
        path,
        '''    def list_audit_events(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> AuditEventListResponse:
        """管理员读取有界审计历史。"""

        current_principal(request).require_administrator()
        return current_administration_service().list_audit_events(limit=limit)
''',
        '''    def list_audit_events(
        request: Request,
        query: Annotated[AuditEventListQuery, Query()],
    ) -> AuditEventListResponse:
        """管理员分页读取完整审计历史。"""

        current_principal(request).require_administrator()
        return current_administration_service().list_audit_events(
            offset=query.offset,
            limit=query.limit,
        )
''',
    )


def patch_historical_retry_fact() -> None:
    contract = "backend/src/aima_ugc/contracts/http.py"
    replace_in_section(
        contract,
        "class HistoricalCampaignResponse(BaseModel):",
        "class HistoricalCampaignListResponse(BaseModel):",
        "    total_rows: int = Field(ge=0)\n",
        "    total_rows: int = Field(ge=0)\n    failed_chunk_count: int = Field(default=0, ge=0)\n",
    )

    repository = "backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py"
    replace_once(
        repository,
        '''    migration_completed_row_count: int
    migration_percent: int
''',
        '''    migration_completed_row_count: int
    migration_percent: int
    failed_chunk_count: int
''',
    )
    replace_once(
        repository,
        '''                ).label("completed_row_count"),
            )
''',
        '''                ).label("completed_row_count"),
                func.count().filter(item.c.status == "failed").label("failed_chunk_count"),
            )
''',
    )
    replace_once(
        repository,
        '''                func.coalesce(chunk_totals.c.completed_row_count, 0).label("completed_row_count"),
            )
''',
        '''                func.coalesce(chunk_totals.c.completed_row_count, 0).label("completed_row_count"),
                func.coalesce(chunk_totals.c.failed_chunk_count, 0).label("failed_chunk_count"),
            )
''',
    )
    replace_once(
        repository,
        '''                migration_percent=_bounded_percent(completed_row_count, total_rows),
            )
''',
        '''                migration_percent=_bounded_percent(completed_row_count, total_rows),
                failed_chunk_count=int(row["failed_chunk_count"]),
            )
''',
    )

    service = "backend/src/aima_ugc/bootstrap/historical_import_http.py"
    replace_once(
        service,
        '''        total_rows=row["total_rows"],
        progress=HistoricalCampaignProgressResponse(
''',
        '''        total_rows=row["total_rows"],
        failed_chunk_count=progress.failed_chunk_count,
        progress=HistoricalCampaignProgressResponse(
''',
    )


def patch_frontend_consumers() -> None:
    path = "frontend/src/features/collection-strategy/store.ts"
    replace_once(
        path,
        '''      let created = await createPack({ name, description })
      for (const text of keywords) {
        created = await addPackKeyword(created.id, { text, priority: 100, enabled: true })
      }
''',
        '''      const created = await createPack({
        name,
        description,
        keywords: keywords.map((text) => ({ text, priority: 100, enabled: true })),
      })
''',
    )

    path = "frontend/src/features/admin-configuration/api.ts"
    replace_once(
        path,
        '''export const fetchAuditEvents = async (): Promise<AuditEventListResponse> =>
  unwrapResponse(await listAuditEvents({ limit: 100 }))
''',
        '''export const fetchAuditEvents = async (
  offset = 0,
  limit = 100,
): Promise<AuditEventListResponse> =>
  unwrapResponse(await listAuditEvents({ offset, limit }))
''',
    )

    path = "frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue"
    replace_once(
        path,
        '''const canRetry = computed(() =>
  ['partial_failed', 'failed'].includes(store.selectedHistoricalCampaign?.status ?? '') &&
  store.historicalCampaignItems.some(
    (item) => item.item_kind === 'chunk' && item.status === 'failed',
  ),
)
''',
        '''const canRetry = computed(() =>
  ['partial_failed', 'failed'].includes(store.selectedHistoricalCampaign?.status ?? '') &&
  (store.selectedHistoricalCampaign?.failed_chunk_count ?? 0) > 0,
)
''',
    )

    path = "frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue"
    replace_once(
        path,
        '''const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
''',
        '''const vehicleFormValid = computed(() => Boolean(
  vehicleDraft.code.trim() && vehicleDraft.displayName.trim(),
))
const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
''',
    )
    replace_once(
        path,
        '              :disabled="saving"\n              @click="saveVehicle"\n',
        '              :disabled="saving || !vehicleFormValid"\n              @click="saveVehicle"\n',
    )


def main() -> None:
    patch_keyword_contract()
    patch_keyword_service()
    patch_audit_contract()
    patch_audit_repository_and_service()
    patch_audit_route()
    patch_historical_retry_fact()
    patch_frontend_consumers()


if __name__ == "__main__":
    main()
