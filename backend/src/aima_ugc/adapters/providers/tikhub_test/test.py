import os

from aima_ugc.adapters.providers.tikhub_test import (
    run_bilibili,
    run_douyin,
    run_kuaishou,
    run_weibo,
    run_xiaohongshu,
)

os.environ.pop("SSLKEYLOGFILE", None)

output = r"./output"

# result = run_xiaohongshu(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     published_within="7d",
#     content_type="all",
#     max_search_pages=10,
#     max_comments_per_content=100,
#     max_replies_per_root=20,
#     output_root=output,
# )

result = run_douyin(
    keywords=("爱玛", "周冠宇"),
    sort_mode="latest",
    published_within="7d",
    duration="all",
    content_type="all",
    max_comments_per_content=100,
    output_root=output,
)
#
# result = run_weibo(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     published_within="week",
#     output_root=output,
# )
#
# result = run_bilibili(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     content_type="video",
#     output_root=output,
# )
#
# result = run_bilibili(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     content_type="video",
#     output_root=output,
# )
#
# result = run_kuaishou(
#     keywords=("爱玛", "爱玛电动车"),
#     output_root=output,
# )
