"""Stage 12 Real Full-stack 专用的本机 OpenAI-compatible 假服务。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class _Handler(BaseHTTPRequestHandler):
    request_no = 0

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return
        self._send_json({"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(length))
        user_payload = json.loads(request["messages"][1]["content"])
        type(self).request_no += 1
        sentiment = "正面" if type(self).request_no % 2 else "负面"
        items = [
            {
                "item_no": item["item_no"],
                "relevance": "relevant",
                "voice_type": "user_voice",
                "sentiment": sentiment,
                "labels": [
                    {
                        "primary_label": "骑行性能",
                        "secondary_label": "舒适性",
                    }
                ],
            }
            for item in user_payload["items"]
        ]
        self._send_json(
            {
                "choices": [
                    {"message": {"content": json.dumps({"items": items}, ensure_ascii=False)}}
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            }
        )

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ThreadingHTTPServer(("127.0.0.1", 8091), _Handler).serve_forever()


if __name__ == "__main__":
    main()
