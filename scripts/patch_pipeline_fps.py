#!/usr/bin/env python3
"""Patch sample_midas_yolo_parallel to publish true fused-pipeline FPS.

The workshop uses QRB ROS Samples PR #429 as an external checkout. This patch is
kept in the attendee repo so prepare_demo_workspace.sh can re-apply it after a
fresh fetch/checkout.
"""

from __future__ import annotations

import argparse
from pathlib import Path


HEADER_INCLUDE_NEEDLE = "#include <std_msgs/msg/header.hpp>\n"
HEADER_INCLUDE_REPLACEMENT = "#include <std_msgs/msg/header.hpp>\n#include <std_msgs/msg/float32.hpp>\n"
HEADER_PUBLISHER_NEEDLE = "  image_transport::Publisher depth_gray_pub_;\n"
HEADER_PUBLISHER_REPLACEMENT = (
    "  image_transport::Publisher depth_gray_pub_;\n"
    "  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pipeline_fps_pub_;\n"
)
HEADER_STATS_NEEDLE = "  std::atomic<uint64_t> processed_count_{ 0 };\n  rclcpp::Time last_log_time_;\n"
HEADER_STATS_REPLACEMENT = (
    "  std::atomic<uint64_t> processed_count_{ 0 };\n"
    "  uint64_t last_fps_count_{ 0 };\n"
    "  rclcpp::Time last_log_time_;\n"
    "  rclcpp::Time last_fps_time_;\n"
)

SOURCE_CTOR_NEEDLE = '  : Node("midas_yolo_fusion_node", options), last_log_time_(this->now())\n'
SOURCE_CTOR_REPLACEMENT = (
    '  : Node("midas_yolo_fusion_node", options), last_log_time_(this->now()), '
    'last_fps_time_(this->now())\n'
)
SOURCE_PUB_NEEDLE = "  depth_gray_pub_ = image_transport::create_publisher(this, \"midas_depth_gray\", image_qos);\n"
SOURCE_PUB_REPLACEMENT = (
    "  depth_gray_pub_ = image_transport::create_publisher(this, \"midas_depth_gray\", image_qos);\n"
    "  pipeline_fps_pub_ = create_publisher<std_msgs::msg::Float32>(\"midas_yolo_pipeline_fps\", 10);\n"
)
SOURCE_FPS_NEEDLE = """    uint64_t cnt = ++processed_count_;
    auto now = this->now();
    if ((now - last_log_time_).seconds() > 2.0) {
"""
SOURCE_FPS_REPLACEMENT = """    uint64_t cnt = ++processed_count_;
    auto now = this->now();
    const double fps_elapsed = (now - last_fps_time_).seconds();
    if (fps_elapsed >= 1.0) {
      std_msgs::msg::Float32 fps_msg;
      fps_msg.data = static_cast<float>((cnt - last_fps_count_) / fps_elapsed);
      pipeline_fps_pub_->publish(fps_msg);
      last_fps_count_ = cnt;
      last_fps_time_ = now;
    }
    if ((now - last_log_time_).seconds() > 2.0) {
"""


def replace_once(path: Path, needle: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    if replacement in text:
        return
    if needle not in text:
        raise RuntimeError(f"patch needle not found in {path}: {needle[:80]!r}")
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def patch_package(samples_dir: Path) -> None:
    package_dir = samples_dir / "ai_vision" / "sample_midas_yolo_parallel"
    header = package_dir / "include" / "sample_midas_yolo_parallel" / "midas_yolo_fusion_node.hpp"
    source = package_dir / "src" / "midas_yolo_fusion_node.cpp"
    if not header.exists() or not source.exists():
        raise RuntimeError(f"sample_midas_yolo_parallel source not found under {samples_dir}")

    replace_once(header, HEADER_INCLUDE_NEEDLE, HEADER_INCLUDE_REPLACEMENT)
    replace_once(header, HEADER_PUBLISHER_NEEDLE, HEADER_PUBLISHER_REPLACEMENT)
    replace_once(header, HEADER_STATS_NEEDLE, HEADER_STATS_REPLACEMENT)
    replace_once(source, SOURCE_CTOR_NEEDLE, SOURCE_CTOR_REPLACEMENT)
    replace_once(source, SOURCE_PUB_NEEDLE, SOURCE_PUB_REPLACEMENT)
    replace_once(source, SOURCE_FPS_NEEDLE, SOURCE_FPS_REPLACEMENT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch QRB sample pipeline FPS publisher")
    parser.add_argument("samples_dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    patch_package(args.samples_dir)
    print("Patched sample_midas_yolo_parallel pipeline FPS publisher.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
