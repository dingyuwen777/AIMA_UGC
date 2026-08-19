import os

from aima_ugc.adapters.providers import tikhub_test

os.environ.pop("SSLKEYLOGFILE", None)

output = r"./output"

# result = tikhub_test.run_xiaohongshu(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     published_within="7d",
#     content_type="all",
#     max_search_pages=10,
#     max_comments_per_content=100,
#     max_replies_per_root=20,
#     output_root=output,
# )

result = tikhub_test.run_douyin(
    keywords=("爱玛", "周冠宇"),
    sort_mode="latest",
    published_within="7d",
    duration="all",
    content_type="all",
    max_comments_per_content=100,
    output_root=output,
)
#
# result = tikhub_test.run_weibo(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     published_within="week",
#     output_root=output,
# )
#
# result = tikhub_test.run_bilibili(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     content_type="video",
#     output_root=output,
# )
#
# result = tikhub_test.run_bilibili(
#     keywords=("爱玛", "爱玛电动车"),
#     sort_mode="latest",
#     content_type="video",
#     output_root=output,
# )
#
# result = tikhub_test.run_kuaishou(
#     keywords=("爱玛", "爱玛电动车"),
#     output_root=output,
# )
