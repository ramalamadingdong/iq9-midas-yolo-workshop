#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSHOP_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
DEMO_REPO_DIR="${DEMO_REPO_DIR:-$WORKSHOP_ROOT/qrb_ros_samples}"

if [ ! -f "$DEMO_REPO_DIR/install/local_setup.bash" ]; then
  echo "Built workspace not found: $DEMO_REPO_DIR/install/local_setup.bash" >&2
  echo "Run ./scripts/prepare_demo_workspace.sh first." >&2
  exit 1
fi

set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1091
source "$DEMO_REPO_DIR/install/local_setup.bash"
set -u

exec ros2 launch sample_midas_yolo_parallel launch_with_usb_cam.py "$@"
