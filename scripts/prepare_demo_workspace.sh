#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSHOP_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
DEMO_REPO_DIR="${DEMO_REPO_DIR:-$WORKSHOP_ROOT/qrb_ros_samples}"
MODEL_SRC="$REPO_ROOT/models/midas_yolo_combined_int8_split.bin"
MODEL_DST=/opt/model/midas_yolo_combined_int8_split.bin
BRANCH=workshop-pr-429

if [ ! -f "$MODEL_SRC" ]; then
  echo "Missing model: $MODEL_SRC" >&2
  exit 1
fi

if [ ! -d "$DEMO_REPO_DIR/.git" ]; then
  git clone https://github.com/qualcomm-qrb-ros/qrb_ros_samples.git "$DEMO_REPO_DIR"
fi

git -C "$DEMO_REPO_DIR" fetch origin pull/429/head
git -C "$DEMO_REPO_DIR" checkout -B "$BRANCH" FETCH_HEAD

sudo mkdir -p /opt/model
sudo cp "$MODEL_SRC" "$MODEL_DST"
sudo chmod 0644 "$MODEL_DST"

cd "$DEMO_REPO_DIR"
# shellcheck disable=SC1091
set +u
source /opt/ros/jazzy/setup.bash
set -u
if [ -f /usr/share/qirp-setup.sh ]; then
  # shellcheck disable=SC1091
  set +u
  source /usr/share/qirp-setup.sh || true
  set -u
fi
colcon build --packages-select sample_midas_yolo_parallel --executor sequential

echo "Demo workspace ready at $DEMO_REPO_DIR"
echo "Model staged at $MODEL_DST"
