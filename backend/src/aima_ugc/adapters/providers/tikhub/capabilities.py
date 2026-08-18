"""TikHub 已由真实响应与生产 Operation 证明的平台业务 Capability。"""

from aima_ugc.contracts.collection import (
    ProviderOperationCapabilityV1,
    ProviderPlatformCapabilityV1,
)

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
            # 生产 Detail/Mapper 当前只闭环 image/video；live 不再对 Plan 暴露伪能力。
            supported_content_types=("all", "video", "image"),
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
            comment_sort_modes=("latest",),
            supports_reply_count=True,
            supports_sub_comments=True,
            supports_incremental_comment_sort=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("get_note_sub_comments",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

DOUYIN_TIKHUB_CAPABILITY = ProviderPlatformCapabilityV1(
    provider="tikhub",
    platform="douyin",
    operations=(
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("fetch_video_search_v2",),
            supported_sort_modes=("general", "most_liked", "latest"),
            supported_time_filters=("all", "1d", "7d", "180d"),
            supported_duration_filters=("all", "under_1m", "1_5m", "over_5m"),
            # 当前 Mapper 只把 video/image 映射为稳定内容类型；article 先关闭公开入口。
            supported_content_types=("all", "video", "image"),
            native_time_filter=True,
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="content_detail",
            provider_operations=("fetch_one_video_v3",),
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="comments",
            provider_operations=("fetch_video_comments",),
            supports_reply_count=True,
            supports_sub_comments=True,
            supports_incremental_comment_sort=False,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("fetch_video_comment_replies",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

WEIBO_TIKHUB_CAPABILITY = ProviderPlatformCapabilityV1(
    provider="tikhub",
    platform="weibo",
    operations=(
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("fetch_search",),
            # TikHub 当前 search_type 是单一维度；生产 Runtime 只批准这三个排序/搜索模式，
            # 不再把 video/image/article 虚构成可与 sort 独立组合的 content_type。
            supported_sort_modes=("general", "latest", "hot"),
            supported_time_filters=("all", "hour", "day", "week", "month"),
            native_time_filter=True,
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="content_detail",
            provider_operations=("fetch_status_detail",),
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="comments",
            provider_operations=("fetch_status_comments",),
            comment_sort_modes=("hot", "latest"),
            supports_reply_count=True,
            supports_sub_comments=True,
            supports_incremental_comment_sort=False,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("fetch_post_sub_comments",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

BILIBILI_TIKHUB_CAPABILITY = ProviderPlatformCapabilityV1(
    provider="tikhub",
    platform="bilibili",
    operations=(
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("fetch_search_by_type",),
            supported_sort_modes=("general", "latest", "play_count", "danmaku_count"),
            supported_content_types=("video",),
            native_time_filter=False,
            observes_comment_count=False,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="content_detail",
            provider_operations=("fetch_one_video",),
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="comments",
            provider_operations=("fetch_video_comments",),
            comment_sort_modes=("latest", "hot"),
            supports_reply_count=True,
            supports_sub_comments=True,
            supports_incremental_comment_sort=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("fetch_reply_detail",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

KUAISHOU_TIKHUB_CAPABILITY = ProviderPlatformCapabilityV1(
    provider="tikhub",
    platform="kuaishou",
    operations=(
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("search_video_v2",),
            supported_content_types=("video",),
            native_time_filter=False,
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="content_detail",
            provider_operations=("fetch_one_video",),
            observes_comment_count=True,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="comments",
            provider_operations=("fetch_video_comment",),
            supports_reply_count=True,
            supports_sub_comments=True,
            supports_incremental_comment_sort=False,
            provider_page_size_policy="provider_default",
        ),
        ProviderOperationCapabilityV1(
            business_operation="sub_comments",
            provider_operations=("fetch_video_sub_comments",),
            provider_page_size_policy="provider_default",
        ),
    ),
)

TIKHUB_PLATFORM_CAPABILITIES = (
    XHS_TIKHUB_CAPABILITY,
    DOUYIN_TIKHUB_CAPABILITY,
    WEIBO_TIKHUB_CAPABILITY,
    BILIBILI_TIKHUB_CAPABILITY,
    KUAISHOU_TIKHUB_CAPABILITY,
)

__all__ = [
    "BILIBILI_TIKHUB_CAPABILITY",
    "DOUYIN_TIKHUB_CAPABILITY",
    "KUAISHOU_TIKHUB_CAPABILITY",
    "TIKHUB_PLATFORM_CAPABILITIES",
    "WEIBO_TIKHUB_CAPABILITY",
    "XHS_TIKHUB_CAPABILITY",
]
