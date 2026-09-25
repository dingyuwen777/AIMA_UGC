#!/usr/bin/env bash
# 清空当前 Compose 数据库的业务数据和 Artifact 实体，仅保留 Alembic 与完整品牌/车型目录。
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
用法：bash reset_keep_vehicle_catalog.sh --env-file /data/AIMA_UGC/env.production [--dry-run | --execute [--yes]]

默认只检查，不修改。--execute 会停止业务容器、备份保留目录、事务性清库并清空 Artifact 实体；
完成后业务容器保持停止。--yes 仅用于明确授权的非交互执行。
原始 Excel 目录、PostgreSQL 数据目录、Secret、日志、env 文件和车型目录不会删除。
USAGE
}

die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
log() { printf '[INFO] %s\n' "$*"; }

ENV_FILE=""
EXECUTE=0
MODE_SET=0
ASSUME_YES=0
while (($#)); do
  case "$1" in
    --env-file) (($# >= 2)) || die '--env-file 缺少路径'; ENV_FILE="$2"; shift 2 ;;
    --dry-run) ((MODE_SET == 0)) || die '运行模式重复'; MODE_SET=1; EXECUTE=0; shift ;;
    --execute) ((MODE_SET == 0)) || die '运行模式重复'; MODE_SET=1; EXECUTE=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数：$1" ;;
  esac
done
[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || die '必须提供现有的 --env-file'
ENV_FILE="$(realpath -e -- "$ENV_FILE")"

for command in docker python3 gzip find findmnt realpath; do
  command -v "$command" >/dev/null 2>&1 || die "缺少命令：$command"
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ -f "$SCRIPT_DIR/compose.yaml" ]]; then
  COMPOSE_DIR="$SCRIPT_DIR"
else
  COMPOSE_DIR="$(realpath -e -- "$SCRIPT_DIR/../..")"
fi
[[ -f "$COMPOSE_DIR/compose.yaml" ]] || die '未找到 canonical compose.yaml'
cd -- "$COMPOSE_DIR"

compose() { docker compose --env-file "$ENV_FILE" "$@"; }
docker info >/dev/null 2>&1 || die '无法访问 Docker daemon'
POSTGRES_ID="$(compose ps -q postgres)"
[[ -n "$POSTGRES_ID" ]] || die '当前 Compose 项目没有运行中的 postgres'

# 从 Compose 已解析挂载读取真实路径，绝不 source 外部 env 文件。
DATA_ROOT="$(compose config --format json | python3 -c '
import json, sys
config = json.load(sys.stdin)
mounts = config["services"]["worker"]["volumes"]
matches = [item["source"] for item in mounts if item["target"] == "/app/data" and item["type"] == "bind"]
if len(matches) != 1:
    raise SystemExit("Worker /app/data 挂载不唯一")
print(matches[0])
')"
[[ -d "$DATA_ROOT" && ! -L "$DATA_ROOT" ]] || die "数据目录无效：$DATA_ROOT"
DATA_ROOT="$(realpath -e -- "$DATA_ROOT")"
ARTIFACT_DIR="$DATA_ROOT/artifacts"
[[ "$DATA_ROOT" != / && "$ARTIFACT_DIR" != / ]] || die '拒绝操作文件系统根目录'
[[ ! -L "$ARTIFACT_DIR" ]] || die 'Artifact 目录不能是符号链接'
[[ ! -e "$ARTIFACT_DIR" || -d "$ARTIFACT_DIR" ]] || die 'Artifact 路径不是目录'

# 嵌套挂载可能越过 ArtifactStore 的删除边界，必须提前拒绝。
while IFS= read -r mount_target; do
  case "$mount_target" in
    "$ARTIFACT_DIR"|"$ARTIFACT_DIR"/*) die "Artifact 目录包含挂载点：$mount_target" ;;
  esac
done < <(findmnt -rn -o TARGET --raw)

db() {
  compose exec -T postgres sh -c \
    'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qAt'
}

MISSING="$(cat <<'SQL' | db
WITH keep(name) AS (
  VALUES ('alembic_version'), ('vehicle_catalog_versions'), ('vehicle_brands'),
         ('vehicle_brand_aliases'), ('vehicle_models'), ('vehicle_model_aliases'),
         ('voice_plaza_projection_state')
)
SELECT COALESCE(string_agg(name, ', ' ORDER BY name), '')
FROM keep WHERE to_regclass(format('public.%I', name)) IS NULL;
SQL
)"
[[ -z "$MISSING" ]] || die "数据库缺少必要表：$MISSING"

UNSAFE="$(cat <<'SQL' | db
SELECT COALESCE(string_agg(format('%I.%I', n.nspname, c.relname), ', '), '')
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind IN ('r','p') AND (c.relkind='p' OR NOT c.relispartition)
  AND n.nspname NOT IN ('public','pg_catalog','information_schema')
  AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp_%';
SQL
)"
[[ -z "$UNSAFE" ]] || die "存在非 public 持久表，拒绝清空：$UNSAFE"

EXTENSION_TABLES="$(cat <<'SQL' | db
SELECT COALESCE(string_agg(c.relname, ', '), '')
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
JOIN pg_depend d ON d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e'
WHERE n.nspname='public' AND c.relkind IN ('r','p');
SQL
)"
[[ -z "$EXTENSION_TABLES" ]] || die "public 存在 Extension 管理的表：$EXTENSION_TABLES"

CATALOG_COUNTS="$(cat <<'SQL' | db
SELECT (SELECT count(*) FROM vehicle_catalog_versions) || '|' ||
       (SELECT count(*) FROM vehicle_brands) || '|' ||
       (SELECT count(*) FROM vehicle_brand_aliases) || '|' ||
       (SELECT count(*) FROM vehicle_models) || '|' ||
       (SELECT count(*) FROM vehicle_model_aliases) || '|' ||
       (SELECT string_agg(version_num, ',' ORDER BY version_num) FROM alembic_version);
SQL
)"
[[ -n "$CATALOG_COUNTS" ]] || die '车型目录或 Alembic 版本状态不可读取'
CATALOG_NONEMPTY="$(cat <<'SQL' | db
SELECT (SELECT count(*) FROM vehicle_catalog_versions) > 0
   AND (SELECT count(*) FROM vehicle_brands) > 0
   AND (SELECT count(*) FROM vehicle_models) > 0
   AND (SELECT count(*) FROM alembic_version) = 1;
SQL
)"
[[ "$CATALOG_NONEMPTY" == t ]] || die '车型目录或 Alembic 版本为空，拒绝清空'
log "保留目录计数（version|brand|brand_alias|model|model_alias|alembic）：$CATALOG_COUNTS"
TARGET_TABLES="$(cat <<'SQL' | db
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
  AND (c.relkind='p' OR NOT c.relispartition)
  AND c.relname<>ALL(ARRAY['alembic_version','vehicle_catalog_versions',
    'vehicle_brands','vehicle_brand_aliases','vehicle_models','vehicle_model_aliases'])
ORDER BY c.relname;
SQL
)"
log "将清空当前 Compose 数据库中除 Alembic 与五张车型目录表外的所有 public 表。"
printf '%s\n' "$TARGET_TABLES"
log "将清空 Artifact 实体目录：$ARTIFACT_DIR"
log '原始 Excel、Secret、env、日志和 PostgreSQL 数据目录不在删除范围。'

if ((EXECUTE == 0)); then
  log 'dry-run 完成；未停止容器、未修改数据库或文件。'
  exit 0
fi
if ((ASSUME_YES == 0)); then
  [[ -t 0 ]] || die '非交互执行必须显式添加 --yes'
  printf '请输入 RESET-AIMA-BUSINESS-DATA 确认：'
  read -r confirmation
  [[ "$confirmation" == RESET-AIMA-BUSINESS-DATA ]] || die '确认文本不匹配'
fi

# 一旦停止写入方，任何失败都保持停止，避免数据库与 Artifact 中间态继续运行。
compose stop frontend api worker scheduler configure migrate
log '业务写入方已停止；失败时请先核对状态，不要直接重启。'

BACKUP_ROOT="$(realpath -m -- "$DATA_ROOT/../../backups")"
mkdir -p -- "$BACKUP_ROOT"
chmod 700 -- "$BACKUP_ROOT"
BACKUP_FILE="$BACKUP_ROOT/vehicle_catalog_$(date +%Y%m%d_%H%M%S).sql.gz"
BACKUP_TMP="$(mktemp "$BACKUP_FILE.tmp.XXXXXX")"
trap 'rm -f -- "$BACKUP_TMP"' EXIT
compose exec -T postgres sh -c '
  exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --no-owner --no-privileges \
    --table=public.vehicle_catalog_versions --table=public.vehicle_brands \
    --table=public.vehicle_brand_aliases --table=public.vehicle_models \
    --table=public.vehicle_model_aliases
' | gzip -c > "$BACKUP_TMP"
[[ -s "$BACKUP_TMP" ]] || die '车型目录备份为空，数据库未清空'
chmod 600 -- "$BACKUP_TMP"
mv -- "$BACKUP_TMP" "$BACKUP_FILE"
log "车型目录备份：$BACKUP_FILE"

# 校验、TRUNCATE 与系统种子恢复属于同一事务；失败自动回滚。
cat <<'SQL' | db
BEGIN;
SET LOCAL lock_timeout = '10s';
DO $reset$
DECLARE
  keep text[] := ARRAY['alembic_version','vehicle_catalog_versions','vehicle_brands',
                       'vehicle_brand_aliases','vehicle_models','vehicle_model_aliases'];
  keep_catalog text[] := ARRAY['vehicle_catalog_versions','vehicle_brands',
                               'vehicle_brand_aliases','vehicle_models','vehicle_model_aliases'];
  unsafe_fk text;
  targets text;
BEGIN
  SELECT string_agg(format('%I -> %I', child.relname, parent.relname), ', ')
    INTO unsafe_fk
  FROM pg_constraint fk JOIN pg_class child ON child.oid=fk.conrelid
  JOIN pg_namespace child_ns ON child_ns.oid=child.relnamespace
  JOIN pg_class parent ON parent.oid=fk.confrelid
  JOIN pg_namespace parent_ns ON parent_ns.oid=parent.relnamespace
  WHERE fk.contype='f' AND child_ns.nspname='public'
    AND child.relname=ANY(keep_catalog)
    AND NOT (parent_ns.nspname='public' AND parent.relname=ANY(keep_catalog));
  IF unsafe_fk IS NOT NULL THEN
    RAISE EXCEPTION '保留目录引用待清空表：%', unsafe_fk;
  END IF;
  SELECT string_agg(format('%I.%I', n.nspname, c.relname), ', ' ORDER BY c.relname)
    INTO targets
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relkind IN ('r','p')
    AND (c.relkind='p' OR NOT c.relispartition) AND c.relname<>ALL(keep);
  IF targets IS NOT NULL THEN
    EXECUTE 'TRUNCATE TABLE ' || targets || ' RESTART IDENTITY';
  END IF;
END $reset$;
INSERT INTO public.voice_plaza_projection_state
    (singleton, status, generation, projected_count, updated_at)
VALUES (true, 'pending', 1, 0, CURRENT_TIMESTAMP)
ON CONFLICT (singleton) DO NOTHING;
DO $verify$
DECLARE
  keep text[] := ARRAY['alembic_version','vehicle_catalog_versions','vehicle_brands',
                       'vehicle_brand_aliases','vehicle_models','vehicle_model_aliases',
                       'voice_plaza_projection_state'];
  item record;
  remaining bigint;
BEGIN
  FOR item IN
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind IN ('r','p')
      AND (c.relkind='p' OR NOT c.relispartition) AND c.relname<>ALL(keep)
  LOOP
    EXECUTE format('SELECT count(*) FROM public.%I', item.relname) INTO remaining;
    IF remaining <> 0 THEN
      RAISE EXCEPTION '业务表 % 未清空，仍有 % 行', item.relname, remaining;
    END IF;
  END LOOP;
END $verify$;
COMMIT;
SQL

AFTER_COUNTS="$(cat <<'SQL' | db
SELECT (SELECT count(*) FROM vehicle_catalog_versions) || '|' ||
       (SELECT count(*) FROM vehicle_brands) || '|' ||
       (SELECT count(*) FROM vehicle_brand_aliases) || '|' ||
       (SELECT count(*) FROM vehicle_models) || '|' ||
       (SELECT count(*) FROM vehicle_model_aliases) || '|' ||
       (SELECT string_agg(version_num, ',' ORDER BY version_num) FROM alembic_version);
SQL
)"
[[ "$AFTER_COUNTS" == "$CATALOG_COUNTS" ]] || die '清空后目录计数异常，业务容器保持停止'

SEED_COUNT="$(printf '%s\n' 'SELECT count(*) FROM voice_plaza_projection_state WHERE singleton AND status='\''pending'\'' AND generation=1;' | db)"
[[ "$SEED_COUNT" == 1 ]] || die '声音广场系统种子恢复失败，业务容器保持停止'

BUSINESS_COUNTS="$(cat <<'SQL' | db
SELECT (SELECT count(*) FROM collection_runs) || '|' ||
       (SELECT count(*) FROM historical_import_campaigns) || '|' ||
       (SELECT count(*) FROM jobs) || '|' ||
       (SELECT count(*) FROM audit_events) || '|' ||
       (SELECT count(*) FROM contents) || '|' ||
       (SELECT count(*) FROM provider_configs) || '|' ||
       (SELECT count(*) FROM artifacts);
SQL
)"
[[ "$BUSINESS_COUNTS" == '0|0|0|0|0|0|0' ]] || \
  die "代表性业务表仍有数据：$BUSINESS_COUNTS，业务容器保持停止"

if [[ -d "$ARTIFACT_DIR" ]]; then
  find "$ARTIFACT_DIR" -xdev -depth -mindepth 1 -delete
  [[ -z "$(find "$ARTIFACT_DIR" -xdev -mindepth 1 -print -quit)" ]] || \
    die 'Artifact 目录仍有残留，业务容器保持停止'
fi

log '业务数据及 Artifact 实体已清空，车型目录与 Alembic 版本保持不变，系统种子已恢复。'
log "验收计数（采集运行|历史导入|Job|管理员审计|Content|Provider|Artifact）：$BUSINESS_COUNTS"
log '业务容器保持停止。请使用本 Release 的 start_compose.py 重新装配 configure 并启动。'
