"""TikHub 当前已实现平台的业务 Capability。"""

from aima_ugc.contracts.collection import (
    ProviderOperationCapabilityV1,
    ProviderPlatformCapabilityV1,
)

# 这里只登记当前 main 已有 Operation/Mapper 且事实源可确认的小红书。
# 抖音、微博、B站、快手必须在各自 Stage 7 实现与 Fixture 验证时再加入机器事实。
XHS_TIKHUB_CAPABILITY = ProviderPlatformCapabilityV1(
    provider="tikhub",
    platform="xhs",
    operations=(
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("search_notes",),
            supported_sort_modes=(
                "general",
                "latest",
                "most_liked",
                "most_commented",
                "most_collected",
                "english_preferred",
            ),
            supported_time_filters=("all", "1d", "7d", "180d"),
            supported_content_types=("all", "video", "image", "live"),
            native_time_filter=True,
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="content_detail",
            provider_operations=("get_image_note_detail", "get_video_note_detail"),
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="comments",
            provider_operations=("get_note_comments",),
            # TikHub 官方还支持 like_count/default，但当前 Stage 6 Operation
            # 把 sort_strategy 固定为 latest_v2，因此当前机器 Capability 只暴露 latest。
            comment_sort_modes=("latest",),
            supports_reply_count=True,
            supports_sub_comments=True,
            # 当前只有非空 Search Fixture。latest_v2 虽由官方文档定义为最新排序，
            # 但尚无非空评论 Fixture/Real Probe 证明“遇到已知 ID 即可安全停止”，
            # 因此不提前宣称可做增量停止。
            supports_incremental_comment_sort=False,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("get_note_sub_comments",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

__all__ = ["XHS_TIKHUB_CAPABILITY"]
