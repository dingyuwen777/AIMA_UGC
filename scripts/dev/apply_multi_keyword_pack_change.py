from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:80]!r}")
    write(path, content.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    content = read(path)
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex expected one match, got {count}: {pattern[:80]!r}")
    write(path, updated)


# 1. HTTP Contract：Manual Discovery 从自由关键词改为多词包。
regex_once(
    "backend/src/aima_ugc/contracts/http.py",
    r'class CollectionRunCreateRequest\(BaseModel\):.*?\n\nclass CollectionRunCreatedResponse',
    '''class CollectionRunCreateRequest(BaseModel):
    """一次性发现从 Keyword Pack 冻结关键词；Batch Supplement 只补既有内容。"""

    model_config = ConfigDict(extra="forbid")

    mode: CollectionRunMode
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    import_batch_id: UUID | None = None
    platforms: tuple[CollectionRunPlatformRequest, ...] = Field(min_length=1, max_length=5)
    include_comments: bool = True
    include_sub_comments: bool = False

    @model_validator(mode="after")
    def validate_mode_and_options(self) -> CollectionRunCreateRequest:
        platforms = [item.platform for item in self.platforms]
        if len(platforms) != len(set(platforms)):
            raise ValueError("同一次 Collection Run 的目标平台不得重复")
        if len(self.keyword_pack_ids) != len(set(self.keyword_pack_ids)):
            raise ValueError("同一次 Collection Run 的词包不得重复")
        if self.mode == "discovery":
            if not self.keyword_pack_ids:
                raise ValueError("主动发现必须选择至少一个 Keyword Pack")
            if self.import_batch_id is not None:
                raise ValueError("主动发现不能关联 Import Batch")
        else:
            if self.import_batch_id is None:
                raise ValueError("基于 Batch 补采必须提供 import_batch_id")
            if self.keyword_pack_ids:
                raise ValueError("基于 Batch 补采不能提交 Keyword Pack")
        if self.include_sub_comments and not self.include_comments:
            raise ValueError("采集二级回复时必须同时启用评论采集")
        return self


class CollectionRunCreatedResponse''',
)

# 2. Import Job：兼容旧 relevance payload，新任务冻结多词包选择。
write(
    "backend/src/aima_ugc/modules/ingestion/import_job.py",
    '''"""Excel Import Job 的版本化 Payload 与共享 Runtime 注册。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

IMPORT_JOB_TYPE = "ingestion.import-excel.v1"
IMPORT_JOB_PAYLOAD_VERSION = "ingestion.import-excel.v1"
IMPORT_JOB_TIMEOUT_SECONDS = 1800
IMPORT_JOB_MAX_ATTEMPTS = 10


class ImportKeywordPackSnapshot(BaseModel):
    """一次 Excel Import 创建时冻结的词包版本身份。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(gt=0)


class ImportKeywordSelectionSnapshot(BaseModel):
    """Excel Import 使用的多词包并集快照；Worker 不再读取实时词包。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["import-keyword-selection.v1"] = "import-keyword-selection.v1"
    keyword_packs: tuple[ImportKeywordPackSnapshot, ...] = Field(min_length=1, max_length=20)
    effective_keywords: tuple[str, ...] = Field(min_length=1)


class ImportJobPayload(BaseModel):
    """兼容旧单词包 Job；新任务使用 keyword_selection 冻结执行输入。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.import-excel.v1"] = "ingestion.import-excel.v1"
    relevance: RelevanceSnapshotV1 | None = None
    keyword_selection: ImportKeywordSelectionSnapshot | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> ImportJobPayload:
        if (self.relevance is None) == (self.keyword_selection is None):
            raise ValueError("Import Job 必须且只能冻结一种关键词快照")
        return self


class ImportJobExecutor(Protocol):
    """正式 Excel Import 业务执行器边界。"""

    def execute(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ImportJobHandler:
    """从当前 Job Fence 进入 Import 链路；Executor 再核对 Payload 与 Batch。"""

    def __init__(self, executor: ImportJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, ImportJobPayload):
            raise TypeError("Import Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_import_job(
    registry: JobRegistry,
    handler: ImportJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """把 Excel Import 注册到现有 PostgreSQL Job Runtime。"""

    registry.register(
        job_type=IMPORT_JOB_TYPE,
        payload_version=IMPORT_JOB_PAYLOAD_VERSION,
        payload_model=ImportJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "IMPORT_JOB_MAX_ATTEMPTS",
    "IMPORT_JOB_PAYLOAD_VERSION",
    "IMPORT_JOB_TIMEOUT_SECONDS",
    "IMPORT_JOB_TYPE",
    "ImportJobExecutor",
    "ImportJobHandler",
    "ImportJobPayload",
    "ImportKeywordPackSnapshot",
    "ImportKeywordSelectionSnapshot",
    "register_import_job",
]
''',
)

# 3. Import Service Protocol 增加词包选择。
replace_once(
    "backend/src/aima_ugc/modules/ingestion/http.py",
    '''        source: BinaryIO,\n        request_id: str,\n    ) -> ImportBatchCreatedResponse: ...''',
    '''        source: BinaryIO,\n        keyword_pack_ids: tuple[UUID, ...],\n        request_id: str,\n    ) -> ImportBatchCreatedResponse: ...''',
)

# 4. Import HTTP：读取多词包快照并冻结到 Batch + Job。
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''from aima_ugc.adapters.persistence.postgres.relevance import (\n    GlobalRelevanceUnavailable,\n    PostgresGlobalRelevanceRepository,\n)''',
    '''from aima_ugc.adapters.persistence.postgres.relevance import (\n    GlobalRelevanceUnavailable,\n    PostgresGlobalRelevanceRepository,\n)\nfrom aima_ugc.adapters.persistence.postgres.scheduled_keywords import (\n    MissingScheduledKeywordPackError,\n    PostgresScheduledKeywordSnapshotReader,\n)''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''from aima_ugc.modules.analysis import normalize_keyword_storage_text''',
    '''from aima_ugc.modules.analysis import (\n    RelevanceKeyword,\n    RelevanceService,\n    normalize_keyword_storage_text,\n)''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''    ImportJobPayload,\n)''',
    '''    ImportJobPayload,\n    ImportKeywordPackSnapshot,\n    ImportKeywordSelectionSnapshot,\n)''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''        source: BinaryIO,\n        request_id: str,\n    ) -> ImportBatchCreatedResponse:\n        del content_type\n        safe_name = _validate_upload_filename(filename)\n        snapshot, _ = self._read_relevance_snapshot()''',
    '''        source: BinaryIO,\n        keyword_pack_ids: tuple[UUID, ...],\n        request_id: str,\n    ) -> ImportBatchCreatedResponse:\n        del content_type\n        safe_name = _validate_upload_filename(filename)\n        selection = self._read_import_keyword_selection(keyword_pack_ids)''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''                    payload=ImportJobPayload(\n                        relevance=snapshot,\n                    ).model_dump(mode="json"),''',
    '''                    payload=ImportJobPayload(\n                        keyword_selection=selection,\n                    ).model_dump(mode="json"),''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    '''                        "relevance": snapshot.model_dump(mode="json"),''',
    '''                        "keyword_selection": selection.model_dump(mode="json"),''',
)
insert_marker = '''    def _read_relevance_snapshot(self) -> tuple[RelevanceSnapshotV1, datetime]:\n'''
insert_block = '''    def _read_import_keyword_selection(\n        self,\n        keyword_pack_ids: tuple[UUID, ...],\n    ) -> ImportKeywordSelectionSnapshot:\n        if not keyword_pack_ids or len(keyword_pack_ids) > 20:\n            raise RelevanceConfigurationError\n        if len(keyword_pack_ids) != len(set(keyword_pack_ids)):\n            raise RelevanceConfigurationError\n        session = self._runtime.database.new_session()\n        try:\n            with session.begin():\n                try:\n                    catalog = PostgresScheduledKeywordSnapshotReader(session).read(keyword_pack_ids)\n                except (MissingScheduledKeywordPackError, ValueError) as exc:\n                    raise RelevanceConfigurationError from exc\n                if any(not pack.enabled for pack in catalog.keyword_packs):\n                    raise RelevanceConfigurationError\n                configured = tuple(\n                    RelevanceKeyword(text=entry.keyword_text, priority=entry.priority)\n                    for entry in catalog.entries\n                    if entry.pack_enabled and entry.keyword_enabled and entry.item_enabled\n                )\n                try:\n                    effective = RelevanceService(configured).effective_keywords\n                except ValueError as exc:\n                    raise RelevanceConfigurationError from exc\n                return ImportKeywordSelectionSnapshot(\n                    keyword_packs=tuple(\n                        ImportKeywordPackSnapshot(id=pack.pack_id, version=pack.version)\n                        for pack in catalog.keyword_packs\n                    ),\n                    effective_keywords=effective,\n                )\n        finally:\n            session.close()\n\n'''
replace_once(
    "backend/src/aima_ugc/bootstrap/import_http.py",
    insert_marker,
    insert_block + insert_marker,
)

# 5. Worker：新任务读取 keyword_selection；旧任务继续读取 relevance。
replace_once(
    "backend/src/aima_ugc/bootstrap/import_worker.py",
    '''            relevance = execution.payload.relevance\n            profile = execution.batch.stats.get("profile")''',
    '''            effective_keywords = _effective_keywords(execution.payload)\n            profile = execution.batch.stats.get("profile")''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_worker.py",
    '''                    keywords=relevance.effective_keywords,''',
    '''                    keywords=effective_keywords,''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_worker.py",
    '''                frozen_relevance = RelevanceSnapshotV1.model_validate(batch.stats.get("relevance"))\n                if frozen_relevance != payload.relevance:\n                    raise ValueError("Import Job Payload 与 Batch Relevance 快照不一致")''',
    '''                if payload.keyword_selection is not None:\n                    frozen_selection = type(payload.keyword_selection).model_validate(\n                        batch.stats.get("keyword_selection")\n                    )\n                    if frozen_selection != payload.keyword_selection:\n                        raise ValueError("Import Job Payload 与 Batch Keyword Selection 快照不一致")\n                else:\n                    frozen_relevance = RelevanceSnapshotV1.model_validate(batch.stats.get("relevance"))\n                    if frozen_relevance != payload.relevance:\n                        raise ValueError("Import Job Payload 与 Batch Relevance 快照不一致")''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/import_worker.py",
    '''def _stat(stats: dict[str, object], name: str) -> int:\n''',
    '''def _effective_keywords(payload: ImportJobPayload) -> tuple[str, ...]:\n    if payload.keyword_selection is not None:\n        return payload.keyword_selection.effective_keywords\n    if payload.relevance is not None:\n        return payload.relevance.effective_keywords\n    raise ValueError("Import Job 缺少关键词快照")\n\n\ndef _stat(stats: dict[str, object], name: str) -> int:\n''',
)

# 6. FastAPI multipart：允许重复 keyword_pack_ids + 一个 file。
replace_once(
    "backend/src/aima_ugc/bootstrap/api.py",
    '''from fastapi import FastAPI, File, Query, Request, Response, UploadFile, status''',
    '''from fastapi import FastAPI, File, Form, Query, Request, Response, UploadFile, status''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/api.py",
    '''        request: Request,\n        file: Annotated[UploadFile, File()],\n    ) -> ImportBatchCreatedResponse:\n        form = await request.form()\n        items = list(form.multi_items())\n        if len(items) != 1 or items[0][0] != "file" or items[0][1] is not file:\n            raise RequestValidationError(\n                [\n                    {\n                        "type": "value_error",\n                        "loc": ("body",),\n                        "msg": "multipart 只允许一个 file 字段",\n                        "input": None,\n                        "ctx": {"error": ValueError("multipart 只允许一个 file 字段")},\n                    }\n                ]\n            )''',
    '''        request: Request,\n        file: Annotated[UploadFile, File()],\n        keyword_pack_ids: Annotated[list[UUID], Form()],\n    ) -> ImportBatchCreatedResponse:\n        form = await request.form()\n        items = list(form.multi_items())\n        allowed = {"file", "keyword_pack_ids"}\n        file_items = [value for key, value in items if key == "file"]\n        pack_items = [value for key, value in items if key == "keyword_pack_ids"]\n        if (\n            any(key not in allowed for key, _ in items)\n            or len(file_items) != 1\n            or file_items[0] is not file\n            or len(pack_items) != len(keyword_pack_ids)\n            or not 1 <= len(keyword_pack_ids) <= 20\n            or len(keyword_pack_ids) != len(set(keyword_pack_ids))\n        ):\n            raise RequestValidationError(\n                [\n                    {\n                        "type": "value_error",\n                        "loc": ("body", "keyword_pack_ids"),\n                        "msg": "multipart 必须包含一个 file 和 1—20 个不重复 keyword_pack_ids",\n                        "input": None,\n                        "ctx": {\n                            "error": ValueError(\n                                "multipart 必须包含一个 file 和 1—20 个不重复 keyword_pack_ids"\n                            )\n                        },\n                    }\n                ]\n            )''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/api.py",
    '''                    source=file.file,\n                    request_id=_request_id(request),''',
    '''                    source=file.file,\n                    keyword_pack_ids=tuple(keyword_pack_ids),\n                    request_id=_request_id(request),''',
)

# 7. Manual Discovery：复用 Scheduled Keyword Catalog + Scope Builder。
replace_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    '''from aima_ugc.adapters.persistence.postgres.relevance import (\n    GlobalRelevanceUnavailable,\n    PostgresGlobalRelevanceRepository,\n)''',
    '''from aima_ugc.adapters.persistence.postgres.relevance import (\n    GlobalRelevanceUnavailable,\n    PostgresGlobalRelevanceRepository,\n)\nfrom aima_ugc.adapters.persistence.postgres.scheduled_keywords import (\n    MissingScheduledKeywordPackError,\n    PostgresScheduledKeywordSnapshotReader,\n)''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    '''from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot''',
    '''from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot\nfrom aima_ugc.modules.collection.scheduled_scopes import build_scheduled_scope_snapshot''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    '''                scopes = self._build_scopes(session, request)\n                if not scopes:\n                    raise CollectionConflict''',
    '''                scopes, keyword_pack_snapshot = self._build_scopes(session, request)\n                if not scopes:\n                    raise CollectionConflict\n                effective_keywords = tuple(\n                    dict.fromkeys(\n                        scope.source_value\n                        for scope in scopes\n                        if scope.source_type == "keyword_search"\n                    )\n                )''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    '''                        "keywords": list(request.keywords),''',
    '''                        "keyword_pack_ids": [str(item) for item in request.keyword_pack_ids],\n                        "keyword_packs": list(keyword_pack_snapshot),\n                        "keywords": list(effective_keywords),''',
)
regex_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    r'    def _build_scopes\(\n        self,\n        session: Session,\n        request: CollectionRunCreateRequest,\n    \) -> tuple\[CollectionScopeDefinition, \.\.\.\]:\n        if request\.mode == "discovery":.*?\n        assert request\.import_batch_id is not None',
    '''    def _build_scopes(\n        self,\n        session: Session,\n        request: CollectionRunCreateRequest,\n    ) -> tuple[tuple[CollectionScopeDefinition, ...], tuple[dict[str, object], ...]]:\n        if request.mode == "discovery":\n            try:\n                catalog = PostgresScheduledKeywordSnapshotReader(session).read(\n                    request.keyword_pack_ids\n                )\n            except (MissingScheduledKeywordPackError, ValueError) as exc:\n                raise CollectionResourceNotFound from exc\n            if any(not pack.enabled for pack in catalog.keyword_packs):\n                raise CollectionConflict\n            snapshot = build_scheduled_scope_snapshot(\n                plan_platforms=tuple(item.platform for item in request.platforms),\n                entries=catalog.entries,\n                keyword_packs=catalog.keyword_packs,\n            )\n            return (\n                snapshot.scopes,\n                tuple(\n                    {"id": str(pack.pack_id), "version": pack.version}\n                    for pack in snapshot.keyword_packs\n                ),\n            )\n        assert request.import_batch_id is not None''',
)
replace_once(
    "backend/src/aima_ugc/bootstrap/collection_http.py",
    '''        return tuple(\n            CollectionScopeDefinition(\n                platform=target.platform,\n                source_type="content",\n                source_value=str(target.content_id),\n                operation_group="content_enrichment",\n            )\n            for target in targets\n        )''',
    '''        return (\n            tuple(\n                CollectionScopeDefinition(\n                    platform=target.platform,\n                    source_type="content",\n                    source_value=str(target.content_id),\n                    operation_group="content_enrichment",\n                )\n                for target in targets\n            ),\n            (),\n        )''',
)

# 8. Frontend API adapter：复用 generated listKeywordPacks。
replace_once(
    "frontend/src/features/import-batches/api.ts",
    '''  listImportBatches,\n  type CollectionCapabilitiesResponse,''',
    '''  listImportBatches,\n  listKeywordPacks,\n  type CollectionCapabilitiesResponse,''',
)
replace_once(
    "frontend/src/features/import-batches/api.ts",
    '''  type ListImportBatchesParams,\n  type ListCollectionRuntimeRunsParams,''',
    '''  type KeywordPackSummaryResponse,\n  type ListImportBatchesParams,\n  type ListCollectionRuntimeRunsParams,''',
)
replace_once(
    "frontend/src/features/import-batches/api.ts",
    '''export async function uploadImportBatch(file: File): Promise<ImportBatchCreatedResponse> {\n  return unwrap(await createImportBatch({ file }))\n}''',
    '''export async function uploadImportBatch(\n  file: File,\n  keywordPackIds: string[],\n): Promise<ImportBatchCreatedResponse> {\n  return unwrap(await createImportBatch({ file, keyword_pack_ids: keywordPackIds }))\n}\n\nexport async function fetchEnabledKeywordPacks(): Promise<KeywordPackSummaryResponse[]> {\n  const response = unwrap(await listKeywordPacks({ enabled: true, limit: 100 }))\n  return response.items\n}''',
)

# 9. Store：加载词包选项，上传携带 ids；Manual Drawer 共用。
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  ImportBatchResponse,\n  ListCollectionRuntimeRunsParams,''',
    '''  ImportBatchResponse,\n  KeywordPackSummaryResponse,\n  ListCollectionRuntimeRunsParams,''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  fetchImportBatchList,\n  ImportApiError,''',
    '''  fetchImportBatchList,\n  fetchEnabledKeywordPacks,\n  ImportApiError,''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  const batchOptions = ref<ImportBatchResponse[]>([])\n  const batchContentPlatforms = ref<CollectionPlatform[]>([])''',
    '''  const batchOptions = ref<ImportBatchResponse[]>([])\n  const keywordPackOptions = ref<KeywordPackSummaryResponse[]>([])\n  const batchContentPlatforms = ref<CollectionPlatform[]>([])''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  const loadingBatchPlatforms = ref(false)\n  const error = ref<string | null>(null)''',
    '''  const loadingBatchPlatforms = ref(false)\n  const loadingKeywordPacks = ref(false)\n  const error = ref<string | null>(null)''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  async function upload(file: File): Promise<ImportBatchCreatedResponse | null> {''',
    '''  async function upload(\n    file: File,\n    keywordPackIds: string[],\n  ): Promise<ImportBatchCreatedResponse | null> {''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''      const created = await uploadImportBatch(file)''',
    '''      const created = await uploadImportBatch(file, keywordPackIds)''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''  async function loadBatchPlatforms(batchId: string): Promise<void> {''',
    '''  async function loadKeywordPacks(): Promise<void> {\n    loadingKeywordPacks.value = true\n    error.value = null\n    try {\n      keywordPackOptions.value = await fetchEnabledKeywordPacks()\n    } catch (reason) {\n      error.value = errorMessage(reason)\n      keywordPackOptions.value = []\n    } finally {\n      loadingKeywordPacks.value = false\n    }\n  }\n\n  async function loadBatchPlatforms(batchId: string): Promise<void> {''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''      const [providerCapabilities, batches] = await Promise.all([\n        fetchCollectionCapabilities(),\n        fetchImportBatchList({ limit: 100 }),\n      ])\n      capabilities.value = providerCapabilities''',
    '''      const [providerCapabilities, batches, packs] = await Promise.all([\n        fetchCollectionCapabilities(),\n        fetchImportBatchList({ limit: 100 }),\n        fetchEnabledKeywordPacks(),\n      ])\n      capabilities.value = providerCapabilities\n      keywordPackOptions.value = packs''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''    batchOptions,\n    batchContentPlatforms,''',
    '''    batchOptions,\n    keywordPackOptions,\n    batchContentPlatforms,''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''    loadingBatchPlatforms,\n    error,''',
    '''    loadingBatchPlatforms,\n    loadingKeywordPacks,\n    error,''',
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    '''    upload,\n    loadBatchPlatforms,''',
    '''    upload,\n    loadKeywordPacks,\n    loadBatchPlatforms,''',
)

# 10. Page：打开上传前加载词包，submit 传 ids；两个 Drawer 接收词包。
replace_once(
    "frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue",
    '''async function upload(file: File): Promise<void> {\n  const created = await store.upload(file)''',
    '''async function openUpload(): Promise<void> {\n  await store.loadKeywordPacks()\n  uploadOpen.value = true\n}\n\nasync function upload(file: File, keywordPackIds: string[]): Promise<void> {\n  const created = await store.upload(file, keywordPackIds)''',
)
replace_once(
    "frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue",
    '''          @click="uploadOpen = true"''',
    '''          @click="openUpload"''',
)
replace_once(
    "frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue",
    '''      :uploading="store.uploading"\n      @submit="upload"''',
    '''      :uploading="store.uploading"\n      :keyword-packs="store.keywordPackOptions"\n      :loading-keyword-packs="store.loadingKeywordPacks"\n      @submit="upload"''',
)
replace_once(
    "frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue",
    '''      :batches="store.batchOptions"\n      :batch-content-platforms="store.batchContentPlatforms"''',
    '''      :batches="store.batchOptions"\n      :keyword-packs="store.keywordPackOptions"\n      :batch-content-platforms="store.batchContentPlatforms"''',
)

# 11. Upload Dialog：多选词包。
write(
    "frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportUploadDialog.vue",
    '''<script setup lang="ts">\nimport { ref, watch } from 'vue'\n\nimport type { KeywordPackSummaryResponse } from '../../../../../generated/api/client'\n\nconst props = defineProps<{\n  modelValue: boolean\n  uploading: boolean\n  keywordPacks: KeywordPackSummaryResponse[]\n  loadingKeywordPacks: boolean\n}>()\nconst emit = defineEmits<{\n  'update:modelValue': [value: boolean]\n  submit: [file: File, keywordPackIds: string[]]\n}>()\nconst selectedFile = ref<File | null>(null)\nconst selectedPackIds = ref<string[]>([])\nconst validationError = ref<string | null>(null)\nconst maxBytes = 500 * 1024 * 1024\n\nwatch(\n  () => props.modelValue,\n  (open) => {\n    if (!open) {\n      selectedFile.value = null\n      selectedPackIds.value = []\n      validationError.value = null\n    }\n  },\n)\n\nfunction selectFile(event: Event): void {\n  const input = event.target as HTMLInputElement\n  const file = input.files?.[0] ?? null\n  validationError.value = null\n  if (file && !file.name.toLocaleLowerCase().endsWith('.xlsx')) {\n    validationError.value = '只支持 .xlsx 文件。'\n    selectedFile.value = null\n    return\n  }\n  if (file && file.size > maxBytes) {\n    validationError.value = 'Excel 文件不能超过 500 MiB。'\n    selectedFile.value = null\n    return\n  }\n  selectedFile.value = file\n}\n\nfunction togglePack(packId: string): void {\n  selectedPackIds.value = selectedPackIds.value.includes(packId)\n    ? selectedPackIds.value.filter((value) => value !== packId)\n    : [...selectedPackIds.value, packId]\n}\n\nfunction submit(): void {\n  if (!selectedFile.value) {\n    validationError.value = '请先选择一个 .xlsx 文件。'\n    return\n  }\n  if (selectedPackIds.value.length === 0) {\n    validationError.value = '请至少选择一个关键词包。'\n    return\n  }\n  emit('submit', selectedFile.value, selectedPackIds.value)\n}\n</script>\n\n<template>\n  <Teleport to="body">\n    <div v-if="modelValue" class="dialog-layer" role="presentation" @click.self="!uploading && emit('update:modelValue', false)">\n      <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="upload-title">\n        <header><h2 id="upload-title">导入 Excel</h2><button type="button" :disabled="uploading" aria-label="关闭导入窗口" @click="emit('update:modelValue', false)">×</button></header>\n        <div class="dialog-body">\n          <p class="description">选择一个或多个关键词包。系统会冻结词包版本，将有效关键词合并去重；标题或正文命中任意关键词即可进入后续去重与入库。</p>\n          <label class="drop-zone">\n            <input type="file" accept=".xlsx" :disabled="uploading" @change="selectFile">\n            <span class="upload-icon">⇧</span><strong>{{ selectedFile?.name || '选择 Excel 文件' }}</strong>\n            <small>单个 .xlsx 最大 500 MiB；实际导入在 Worker 中继续执行。</small>\n          </label>\n          <section class="pack-section">\n            <strong>关键词包（可多选）</strong>\n            <p v-if="loadingKeywordPacks" class="pack-state">正在加载词包…</p>\n            <p v-else-if="keywordPacks.length === 0" class="pack-state">当前没有可用的已启用词包。</p>\n            <div v-else class="pack-list">\n              <label v-for="pack in keywordPacks" :key="pack.id" class="pack-item">\n                <input type="checkbox" :checked="selectedPackIds.includes(pack.id)" :disabled="uploading" @change="togglePack(pack.id)">\n                <span><b>{{ pack.name }}</b><small>{{ pack.keyword_count }} 个关键词 · v{{ pack.version }}</small></span>\n              </label>\n            </div>\n          </section>\n          <p v-if="validationError" class="validation-error">{{ validationError }}</p>\n        </div>\n        <footer>\n          <button class="dialog-button" type="button" :disabled="uploading" @click="emit('update:modelValue', false)">取消</button>\n          <button class="dialog-button dialog-button--primary" type="button" :disabled="uploading || loadingKeywordPacks || keywordPacks.length === 0" @click="submit">{{ uploading ? '正在创建…' : '开始导入' }}</button>\n        </footer>\n      </section>\n    </div>\n  </Teleport>\n</template>\n\n<style scoped>\n.dialog-layer { position: fixed; inset: 0; z-index: 120; display: grid; place-items: center; background: rgb(22 29 43 / 45%); }\n.dialog { width: 560px; max-height: 86vh; overflow: hidden; border-radius: 10px; background: #fff; box-shadow: 0 18px 60px rgb(22 29 43 / 20%); }\n.dialog header { display: flex; height: 58px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }\n.dialog h2 { margin: 0; font-size: 18px; }\n.dialog header button { border: 0; color: #596275; background: transparent; cursor: pointer; font-size: 24px; }\n.dialog-body { max-height: calc(86vh - 130px); overflow: auto; padding: 22px; }\n.dialog footer { padding: 14px 22px; border-top: 1px solid var(--aima-border); text-align: right; }\n.description { margin-top: 0; color: #657087; font-size: 13px; line-height: 1.7; }\n.drop-zone { display: flex; min-height: 150px; align-items: center; flex-direction: column; justify-content: center; border: 1px dashed #ff7fac; border-radius: 9px; background: #fff9fb; cursor: pointer; }\n.drop-zone input { position: absolute; width: 1px; height: 1px; opacity: 0; }\n.upload-icon { display: grid; width: 42px; height: 42px; margin-bottom: 12px; place-items: center; border-radius: 50%; color: #fff; background: var(--aima-primary); font-size: 23px; }\n.drop-zone strong { max-width: 450px; overflow: hidden; color: #313a4c; text-overflow: ellipsis; white-space: nowrap; }\n.drop-zone small { margin-top: 8px; color: #8992a3; }\n.pack-section { margin-top: 18px; }\n.pack-section > strong { color: #313a4c; font-size: 14px; }\n.pack-state { color: #8992a3; font-size: 13px; }\n.pack-list { display: grid; gap: 8px; max-height: 210px; margin-top: 10px; overflow: auto; }\n.pack-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border: 1px solid #e1e5ec; border-radius: 7px; cursor: pointer; }\n.pack-item span { display: grid; gap: 3px; }\n.pack-item b { color: #313a4c; font-size: 13px; }\n.pack-item small { color: #8992a3; font-size: 12px; }\n.validation-error { color: var(--aima-danger); font-size: 13px; }\n.dialog-button { height: 38px; padding: 0 22px; border: 1px solid #d9dee8; border-radius: 6px; background: #fff; cursor: pointer; }\n.dialog-button--primary { margin-left: 10px; border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }\n.dialog-button:disabled { cursor: wait; opacity: .65; }\n</style>\n''',
)

# 12. TikHub Drawer：独立发现改成多词包选择；Batch Supplement 不变。
path = "frontend/src/features/import-batches/pages/CollectionRuntimePage/components/TikHubSupplementDrawer.vue"
content = read(path)
content = content.replace(
    '''  ImportBatchResponse,\n} from '../../../../../generated/api/client' ''',
    '''  ImportBatchResponse,\n  KeywordPackSummaryResponse,\n} from '../../../../../generated/api/client' ''',
)
# 上面的精确尾部可能不含空格，单独兜底。
if "KeywordPackSummaryResponse" not in content:
    content = content.replace(
        "  ImportBatchResponse,\n} from '../../../../../generated/api/client'",
        "  ImportBatchResponse,\n  KeywordPackSummaryResponse,\n} from '../../../../../generated/api/client'",
        1,
    )
content = content.replace(
    '''  batches: ImportBatchResponse[]\n  batchContentPlatforms: CollectionPlatform[]''',
    '''  batches: ImportBatchResponse[]\n  keywordPacks: KeywordPackSummaryResponse[]\n  batchContentPlatforms: CollectionPlatform[]''',
    1,
)
content = content.replace("const keywordInput = ref('')\nconst keywords = ref<string[]>([])\n", "const selectedPackIds = ref<string[]>([])\n", 1)
content = content.replace(
    "  if (mode.value === 'discovery') return keywords.value.length > 0 || keywordInput.value.trim().length > 0",
    "  if (mode.value === 'discovery') return selectedPackIds.value.length > 0",
    1,
)
content = content.replace("    keywordInput.value = ''\n    keywords.value = []\n", "    selectedPackIds.value = []\n", 1)
content = re.sub(r'\nfunction addKeywords\(\): void \{.*?\n\}\n\nfunction togglePlatform', '\nfunction togglePack(packId: string): void {\n  selectedPackIds.value = selectedPackIds.value.includes(packId)\n    ? selectedPackIds.value.filter((value) => value !== packId)\n    : [...selectedPackIds.value, packId]\n}\n\nfunction togglePlatform', content, count=1, flags=re.S)
content = content.replace("  addKeywords()\n", "", 1)
content = content.replace(
    "  if (mode.value === 'discovery' && keywords.value.length === 0) {\n    validation.value = '请输入至少一个一次性 Discovery 关键词。'",
    "  if (mode.value === 'discovery' && selectedPackIds.value.length === 0) {\n    validation.value = '请至少选择一个 Discovery 关键词包。'",
    1,
)
content = content.replace(
    "    keywords: mode.value === 'discovery' ? keywords.value : [],",
    "    keyword_pack_ids: mode.value === 'discovery' ? selectedPackIds.value : [],",
    1,
)
content = content.replace(
    "输入一次性 Discovery 关键词，主动从平台发现帖子；关键词仅冻结到本次 Run。",
    "选择一个或多个 Discovery 词包；系统冻结词包版本并展开有效关键词到本次 Run。",
    1,
)
content = re.sub(
    r'''        <section v-if="mode === 'discovery'">.*?        </section>\n        <section v-else>''',
    '''        <section v-if="mode === 'discovery'">\n          <label>Discovery 关键词包（可多选）</label>\n          <div class="keyword-box pack-choice-list">\n            <label v-for="pack in keywordPacks" :key="pack.id" class="pack-choice">\n              <input type="checkbox" :checked="selectedPackIds.includes(pack.id)" @change="togglePack(pack.id)">\n              <span>{{ pack.name }} · {{ pack.keyword_count }} 词 · v{{ pack.version }}</span>\n            </label>\n          </div>\n          <p v-if="keywordPacks.length === 0" class="platform-state">当前没有可用的已启用词包。</p>\n        </section>\n        <section v-else>''',
    content,
    count=1,
    flags=re.S,
)
# 为复选列表补轻量样式（若已有 keyword-box 样式则追加）。
content = content.replace(
    "</style>",
    ".pack-choice-list { display: grid; gap: 8px; padding: 10px; }\n.pack-choice { display: flex; gap: 8px; align-items: center; color: #394255; font-size: 13px; }\n</style>",
    1,
)
write(path, content)

# 13. API tests：multipart 必须提交 keyword_pack_ids，并验证 service 收到选择。
path = "tests/api/test_stage8b_imports.py"
content = read(path)
content = content.replace("        self.created_file = b\"\"\n", "        self.created_file = b\"\"\n        self.created_keyword_pack_ids: tuple[UUID, ...] = ()\n", 1)
content = content.replace(
    '''        source: BytesIO,\n        request_id: str,\n    ) -> ImportBatchCreatedResponse:\n        del filename, content_type, request_id''',
    '''        source: BytesIO,\n        keyword_pack_ids: tuple[UUID, ...],\n        request_id: str,\n    ) -> ImportBatchCreatedResponse:\n        del filename, content_type, request_id\n        self.created_keyword_pack_ids = keyword_pack_ids''',
    1,
)
content = content.replace(
    '''        files={"file": ("input.xlsx", b"xlsx", "application/octet-stream")},\n    )''',
    '''        files=[\n            ("file", ("input.xlsx", b"xlsx", "application/octet-stream")),\n            ("keyword_pack_ids", (None, str(service.pack_id))),\n        ],\n    )''',
    1,
)
content = content.replace("    assert service.created_file == b\"xlsx\"\n", "    assert service.created_file == b\"xlsx\"\n    assert service.created_keyword_pack_ids == (service.pack_id,)\n", 1)
content = content.replace(
    '''        files={"file": ("bad.xlsx", b"bad", "application/octet-stream")},\n    )''',
    '''        files=[\n            ("file", ("bad.xlsx", b"bad", "application/octet-stream")),\n            ("keyword_pack_ids", (None, str(service.pack_id))),\n        ],\n    )''',
    1,
)
write(path, content)

# 14. Stage 8E API tests：Discovery 改用 keyword_pack_ids 的 Contract；Fake Service 只需接收新字段。
path = "tests/api/test_stage8e_collection_runs.py"
content = read(path)
content = re.sub(r'"keywords": \[[^\]]+\],', '"keyword_pack_ids": [str(uuid4())],', content)
write(path, content)

# 15. 文档同步：明确三个入口的词包语义。
path = "docs/appendix/08_数据入口与统一入库实现.md"
content = read(path)
content = content.replace(
    '''正式 Excel Import 在进入 Content 前使用规则 Relevance：\n\n```text\n全局 Relevance Config\n→ Keyword Pack\n→ effective_keywords\n→ filter_canonical_content_jsonl()\n```''',
    '''正式 Excel Import 在进入 Content 前使用规则 Relevance。上传时必须选择一个或多个已启用 Keyword Pack；API 创建 Batch/Job 时冻结所选词包版本，并把各词包有效关键词合并、去重为 `effective_keywords`：\n\n```text\nExcel Upload\n→ selected Keyword Packs (1..20)\n→ frozen pack id/version\n→ effective_keywords 并集去重\n→ title/text 任一关键词 OR 匹配\n→ filter_canonical_content_jsonl()\n```''',
    1,
)
content += '''\n\n## 多词包入口一致性（2026-08）\n\n当前主动按关键词处理内容的三个入口统一为 Keyword Pack 选择：\n\n```text\nExcel Import\nTikHub Manual Discovery\nCollection Plan\n→ 选择一个或多个 Keyword Pack\n→ 冻结词包版本\n→ 展开有效关键词\n```\n\nExcel Import 对标题/正文执行关键词并集 OR 过滤；TikHub Manual Discovery 和 Collection Plan 按目标平台与 `platform_scope` 展开搜索 Scope。`batch_supplement` 针对已有 Batch 内容补详情/评论，不接收 Keyword Pack，也不执行关键词搜索。\n'''
write(path, content)

print("multi keyword pack patch applied")
