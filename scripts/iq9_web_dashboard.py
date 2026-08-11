#!/usr/bin/env python3
"""Serve the IQ9 workshop browser dashboard.

The dashboard embeds MJPEG streams from ROS web_video_server so attendees can
watch the raw camera, MiDaS depth, and MiDaS+YOLO overlay from one page. When
ROS Python APIs are available, it also subscribes to the displayed image topics
and reports live processing FPS.
"""

from __future__ import annotations

import argparse
import html
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
except ImportError:  # Dashboard still serves static streams if ROS Python is unavailable.
    rclpy = None  # type: ignore[assignment]
    Node = object  # type: ignore[assignment,misc]
    qos_profile_sensor_data = 10  # type: ignore[assignment]
    Image = object  # type: ignore[assignment,misc]


DEFAULT_CAMERA_TOPIC = "/image_raw"
DEFAULT_DEPTH_TOPIC = "/midas_depth_gray"
DEFAULT_OVERLAY_TOPIC = "/midas_yolo_overlay"
FPS_WINDOW_SECONDS = 5.0


def stream_url(video_host: str, video_port: int, topic: str, qos_profile: str) -> str:
    return (
        f"http://{video_host}:{video_port}/stream"
        f"?topic={quote(topic)}&type=mjpeg&qos_profile={quote(qos_profile)}"
    )


class FpsMonitor:
    def __init__(self, topics: list[str], reliable_topics: list[str], window_seconds: float = FPS_WINDOW_SECONDS) -> None:
        self._topics = list(dict.fromkeys(topics))
        self._reliable_topics = set(reliable_topics)
        self._window_seconds = window_seconds
        self._samples: dict[str, deque[float]] = {topic: deque() for topic in self._topics}
        self._lock = threading.Lock()
        self._node: Node | None = None
        self._thread: threading.Thread | None = None
        self._error = ""

    def start(self) -> None:
        if rclpy is None:
            self._error = "rclpy unavailable; FPS metrics disabled"
            return
        try:
            if not rclpy.ok():
                rclpy.init(args=None)
            self._node = rclpy.create_node("iq9_web_dashboard_fps")
            for topic in self._topics:
                qos_profile = 10 if topic in self._reliable_topics else qos_profile_sensor_data
                self._node.create_subscription(Image, topic, self._callback_for(topic), qos_profile)
            self._thread = threading.Thread(target=rclpy.spin, args=(self._node,), daemon=True)
            self._thread.start()
        except Exception as exc:  # Keep dashboard usable even if ROS graph is unavailable.
            self._error = f"FPS metrics disabled: {exc}"

    def _callback_for(self, topic: str) -> Any:
        def callback(_: Image) -> None:
            now = time.monotonic()
            with self._lock:
                samples = self._samples[topic]
                samples.append(now)
                cutoff = now - self._window_seconds
                while samples and samples[0] < cutoff:
                    samples.popleft()

        return callback

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        topics: dict[str, dict[str, Any]] = {}
        with self._lock:
            for topic, samples in self._samples.items():
                if len(samples) >= 2:
                    elapsed = samples[-1] - samples[0]
                    fps = (len(samples) - 1) / elapsed if elapsed > 0 else 0.0
                    age = now - samples[-1]
                elif len(samples) == 1:
                    fps = 0.0
                    age = now - samples[-1]
                else:
                    fps = None
                    age = None
                topics[topic] = {
                    "fps": None if fps is None else round(fps, 1),
                    "frames": len(samples),
                    "last_age_seconds": None if age is None else round(age, 2),
                }
        return {"ok": not self._error, "error": self._error, "topics": topics}


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
        ("Camera", camera_topic, camera_qos_profile, "Raw USB camera feed"),
        ("MiDaS depth", depth_topic, default_qos_profile, "Grayscale depth output"),
        ("MiDaS + YOLO", overlay_topic, default_qos_profile, "Detection/segmentation overlay"),
    ]
    cards = []
    for title, topic, stream_qos_profile, description in streams:
        src = stream_url(video_host, video_port, topic, stream_qos_profile)
        escaped_topic = html.escape(topic, quote=True)
        cards.append(
            f"""
            <section class="card">
              <div class="card-header">
                <div>
                  <h2>{html.escape(title)}</h2>
                  <code>{html.escape(topic)}</code>
                </div>
                <div class="fps" data-topic="{escaped_topic}">FPS --</div>
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
  <title>IQ9 MiDaS + YOLO Live Output</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #08111f; color: #edf4ff; }}
    header {{ padding: 1.25rem 1.5rem; background: linear-gradient(135deg, #14213d, #0b5f89); }}
    h1 {{ margin: 0 0 .35rem; font-size: clamp(1.5rem, 3vw, 2.5rem); }}
    header p {{ margin: 0; color: #d2e8ff; }}
    main {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); padding: 1rem; }}
    .card {{ background: #101b2d; border: 1px solid #27415f; border-radius: 16px; overflow: hidden; box-shadow: 0 14px 40px rgba(0, 0, 0, .28); }}
    .card-header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; padding: 1rem 1rem 0; }}
    h2 {{ margin: 0; font-size: 1.2rem; }}
    code {{ color: #8bd3ff; font-size: .82rem; overflow-wrap: anywhere; }}
    .fps {{ flex: 0 0 auto; border: 1px solid #3b638c; border-radius: 999px; padding: .25rem .6rem; background: #07111e; color: #bfe7ff; font-weight: 700; font-variant-numeric: tabular-nums; }}
    .fps.stale {{ color: #ffd38b; border-color: #8c6b3b; }}
    .card p {{ margin: .4rem 1rem 1rem; color: #b9c7d9; }}
    img {{ display: block; width: 100%; min-height: 240px; max-height: 70vh; object-fit: contain; background: #03070d; }}
    footer {{ padding: 0 1rem 1rem; color: #b9c7d9; font-size: .9rem; }}
    a {{ color: #8bd3ff; }}
  </style>
</head>
<body>
  <header>
    <h1>IQ9 MiDaS + YOLO Live Output</h1>
    <p>Live USB camera, MiDaS depth, YOLO overlay, and per-topic processing FPS.</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
  <footer>
    Stream source: <a href="http://{html.escape(video_host)}:{video_port}/">web_video_server</a> · Camera QoS: <code>{html.escape(camera_qos_profile)}</code> · Output QoS: <code>{html.escape(default_qos_profile)}</code> · Metrics: <code>/status</code>
  </footer>
  <script>
    async function refreshFps() {{
      try {{
        const response = await fetch('/status', {{cache: 'no-store'}});
        const payload = await response.json();
        document.querySelectorAll('[data-topic]').forEach((element) => {{
          const topic = element.dataset.topic;
          const metric = payload.topics[topic];
          if (!metric || metric.fps === null) {{
            element.textContent = 'FPS --';
            element.classList.add('stale');
            return;
          }}
          element.textContent = `${{metric.fps.toFixed(1)}} FPS`;
          element.classList.toggle('stale', metric.last_age_seconds > 2.0);
        }});
      }} catch (error) {{
        document.querySelectorAll('[data-topic]').forEach((element) => {{
          element.textContent = 'FPS --';
          element.classList.add('stale');
        }});
      }}
    }}
    refreshFps();
    setInterval(refreshFps, 1000);
  </script>
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

        if self.path == "/status":
            content = json.dumps(self.server.fps_monitor.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
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
        fps_monitor: FpsMonitor,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.video_port = video_port
        self.default_qos_profile = default_qos_profile
        self.camera_qos_profile = camera_qos_profile
        self.camera_topic = camera_topic
        self.depth_topic = depth_topic
        self.overlay_topic = overlay_topic
        self.fps_monitor = fps_monitor


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
    fps_monitor = FpsMonitor([args.camera_topic, args.depth_topic, args.overlay_topic], reliable_topics=[args.camera_topic])
    fps_monitor.start()
    server = DashboardServer(
        (args.address, args.port),
        DashboardHandler,
        video_port=args.video_port,
        default_qos_profile=args.qos_profile,
        camera_qos_profile=args.camera_qos_profile,
        camera_topic=args.camera_topic,
        depth_topic=args.depth_topic,
        overlay_topic=args.overlay_topic,
        fps_monitor=fps_monitor,
    )
    print(f"IQ9 dashboard serving on http://{args.address}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
