#!/usr/bin/env python3
"""Serve the IQ9 workshop browser dashboard.

The dashboard is intentionally dependency-free. It embeds MJPEG streams from
ROS web_video_server so attendees can watch the raw camera, MiDaS depth, and
MiDaS+YOLO overlay from one page.
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
    qos_profile: str,
    camera_topic: str,
    depth_topic: str,
    overlay_topic: str,
) -> bytes:
    video_host = request_host.split(":", 1)[0] or "127.0.0.1"
    streams = [
        ("Camera", camera_topic, "Raw USB camera feed"),
        ("MiDaS depth", depth_topic, "Grayscale depth output"),
        ("MiDaS + YOLO", overlay_topic, "Detection/segmentation overlay"),
    ]
    cards = []
    for title, topic, description in streams:
        src = stream_url(video_host, video_port, topic, qos_profile)
        cards.append(
            f"""
            <section class="card">
              <div class="card-header">
                <h2>{html.escape(title)}</h2>
                <code>{html.escape(topic)}</code>
              </div>
              <p>{html.escape(description)}</p>
              <img src="{html.escape(src, quote=True)}" alt="{html.escape(title)} live stream" />
            </section>
            """
        )

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="refresh" content="300" />
  <title>IQ9 MiDaS + YOLO Live Output</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #08111f; color: #edf4ff; }}
    header {{ padding: 1.25rem 1.5rem; background: linear-gradient(135deg, #14213d, #0b5f89); }}
    h1 {{ margin: 0 0 .35rem; font-size: clamp(1.5rem, 3vw, 2.5rem); }}
    header p {{ margin: 0; color: #d2e8ff; }}
    main {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); padding: 1rem; }}
    .card {{ background: #101b2d; border: 1px solid #27415f; border-radius: 16px; overflow: hidden; box-shadow: 0 14px 40px rgba(0, 0, 0, .28); }}
    .card-header {{ display: flex; align-items: baseline; justify-content: space-between; gap: .75rem; padding: 1rem 1rem 0; }}
    h2 {{ margin: 0; font-size: 1.2rem; }}
    code {{ color: #8bd3ff; font-size: .82rem; overflow-wrap: anywhere; }}
    .card p {{ margin: .4rem 1rem 1rem; color: #b9c7d9; }}
    img {{ display: block; width: 100%; min-height: 240px; max-height: 70vh; object-fit: contain; background: #03070d; }}
    footer {{ padding: 0 1rem 1rem; color: #b9c7d9; font-size: .9rem; }}
    a {{ color: #8bd3ff; }}
  </style>
</head>
<body>
  <header>
    <h1>IQ9 MiDaS + YOLO Live Output</h1>
    <p>Live USB camera, MiDaS depth, and YOLO overlay streams from ROS web_video_server.</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
  <footer>
    Stream source: <a href="http://{html.escape(video_host)}:{video_port}/">web_video_server</a> · QoS profile: <code>{html.escape(qos_profile)}</code>
  </footer>
</body>
</html>
"""
    return body.encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    server: "DashboardServer"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return

        content = render_dashboard(
            request_host=self.headers.get("Host", "127.0.0.1"),
            video_port=self.server.video_port,
            qos_profile=self.server.qos_profile,
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

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


class DashboardServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        video_port: int,
        qos_profile: str,
        camera_topic: str,
        depth_topic: str,
        overlay_topic: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.video_port = video_port
        self.qos_profile = qos_profile
        self.camera_topic = camera_topic
        self.depth_topic = depth_topic
        self.overlay_topic = overlay_topic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the IQ9 web dashboard")
    parser.add_argument("--address", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--video-port", type=int, default=8080)
    parser.add_argument("--qos-profile", default="sensor_data")
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
        qos_profile=args.qos_profile,
        camera_topic=args.camera_topic,
        depth_topic=args.depth_topic,
        overlay_topic=args.overlay_topic,
    )
    print(f"IQ9 dashboard serving on http://{args.address}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
