"""一次性补齐 Stage 2 车型品牌选择控件的显式 accessible name；由 workflow 验证后删除。"""

from pathlib import Path

path = Path("frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue")
text = path.read_text(encoding="utf-8")
old = '            <select v-model="vehicleDraft.brandId">\n'
new = '            <select\n              v-model="vehicleDraft.brandId"\n              aria-label="品牌"\n            >\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected exactly one Brand select match, got {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Stage 2 Brand select accessible name patched")
