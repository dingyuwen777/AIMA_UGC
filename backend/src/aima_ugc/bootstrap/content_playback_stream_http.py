"""把浏览器断开传播给拥有上游连接的同源视频响应。"""

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from aima_ugc.adapters.providers.video_stream import VideoStreamHandle


class ContentVideoStreamingResponse(StreamingResponse):
    """流完成、发送失败、任务取消或 disconnect 都显式释放上游。"""

    def __init__(self, handle: VideoStreamHandle) -> None:
        super().__init__(
            handle.iter_bytes(), status_code=handle.status_code, headers=handle.headers
        )
        self._handle = handle

    async def listen_for_disconnect(self, receive: Receive) -> None:
        """旧 ASGI 版本的断开监听同时关闭正在读取的同步响应。"""
        try:
            await super().listen_for_disconnect(receive)
        finally:
            self._handle.close()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """新 ASGI 的发送异常也不能依赖生成器被回收才释放连接。"""
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._handle.close()
