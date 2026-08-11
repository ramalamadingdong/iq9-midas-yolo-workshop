#!/usr/bin/env python3
"""Serve the IQ9 workshop browser dashboard.

The dashboard embeds MJPEG streams from ROS web_video_server so attendees can
watch the raw camera, MiDaS depth, and MiDaS+YOLO overlay from one page.
"""

from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


DEFAULT_CAMERA_TOPIC = "/image_raw"
DEFAULT_DEPTH_TOPIC = "/midas_depth_gray"
DEFAULT_OVERLAY_TOPIC = "/midas_yolo_overlay"


def stream_url(video_host: str, video_port: int, topic: str, qos_profile: str) -> str:
    return (
        f"http://{video_host}:{video_port}/stream"
        f"?topic={quote(topic)}&type=mjpeg&qos_profile={quote(qos_profile)}"
    )


def render_dashboard(
    *,
    request_host: str,
    video_port: int,
    default_qos_profile: str,
    camera_qos_profile: str,
    camera_topic: str,
    depth_topic: str,
    overlay_topic: str,
) -> bytes:
    video_host = request_host.split(":", 1)[0] or "127.0.0.1"
    streams = [
        (camera_topic, camera_qos_profile),
        (depth_topic, default_qos_profile),
        (overlay_topic, default_qos_profile),
    ]
    cards = []
    for topic, stream_qos_profile in streams:
        src = stream_url(video_host, video_port, topic, stream_qos_profile)
        cards.append(
            f"""
            <section class="card">
              <img src="{html.escape(src, quote=True)}" alt="" />
            </section>
            """
        )

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title></title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; background: #03070d; }}
    main {{ display: grid; gap: .75rem; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); min-height: 100vh; padding: .75rem; box-sizing: border-box; }}
    .card {{ display: flex; align-items: center; justify-content: center; min-height: 30vh; background: #03070d; border-radius: 16px; overflow: hidden; }}
    img {{ display: block; width: 100%; height: 100%; min-height: 30vh; max-height: 100vh; object-fit: contain; background: #03070d; }}
  </style>
</head>
<body>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    return body.encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    server: "DashboardServer"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path in ("/", "/index.html"):
            content = render_dashboard(
                request_host=self.headers.get("Host", "127.0.0.1"),
                video_port=self.server.video_port,
                default_qos_profile=self.server.default_qos_profile,
                camera_qos_profile=self.server.camera_qos_profile,
                camera_topic=self.server.camera_topic,
                depth_topic=self.server.depth_topic,
                overlay_topic=self.server.overlay_topic,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


class DashboardServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        video_port: int,
        default_qos_profile: str,
        camera_qos_profile: str,
        camera_topic: str,
        depth_topic: str,
        overlay_topic: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.video_port = video_port
        self.default_qos_profile = default_qos_profile
        self.camera_qos_profile = camera_qos_profile
        self.camera_topic = camera_topic
        self.depth_topic = depth_topic
        self.overlay_topic = overlay_topic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the IQ9 web dashboard")
    parser.add_argument("--address", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--video-port", type=int, default=8080)
    parser.add_argument("--qos-profile", default="sensor_data")
    parser.add_argument("--camera-qos-profile", default="default")
    parser.add_argument("--camera-topic", default=DEFAULT_CAMERA_TOPIC)
    parser.add_argument("--depth-topic", default=DEFAULT_DEPTH_TOPIC)
    parser.add_argument("--overlay-topic", default=DEFAULT_OVERLAY_TOPIC)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = DashboardServer(
        (args.address, args.port),
        DashboardHandler,
        video_port=args.video_port,
        default_qos_profile=args.qos_profile,
        camera_qos_profile=args.camera_qos_profile,
        camera_topic=args.camera_topic,
        depth_topic=args.depth_topic,
        overlay_topic=args.overlay_topic,
    )
    print(f"IQ9 dashboard serving on http://{args.address}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
