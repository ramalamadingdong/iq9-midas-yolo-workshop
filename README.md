# IQ9 Parallel Depth + Segmentation Workshop

Run a real-time robotics perception demo on Qualcomm Dragonwing IQ-9075 EVK (**IQ9**) with ROS 2 Jazzy, QRB ROS, QNN/HTP inference, MiDaS depth, and YOLO11n segmentation.

This repository is the attendee-facing workshop package. Clone it on the IQ9, run the setup scripts, plug in a USB camera, and launch the demo.

## What you will build and run

```text
USB camera /image_raw
        ↓
MidasYoloFusionNode
  - preprocesses MiDaS depth tensor
  - preprocesses YOLO segmentation tensor
        ↓
QrbRosSharedInferenceNode
  - loads one shared QNN context binary
  - graph 0: midas
  - graph 1: yolov11_seg
        ↓
MidasYoloFusionNode
  - matches outputs by timestamp
  - decodes depth, detections, masks
        ↓
/midas_depth_map
/midas_depth_gray
/midas_yolo_overlay
```

The demo source comes from Qualcomm QRB ROS Samples PR #429: `sample_midas_yolo_parallel`.

## Why this is a QRB ROS workshop

QRB ROS keeps the application in normal ROS 2 concepts while exposing Qualcomm robotics acceleration paths.

| Robotics problem | Stock ROS 2 default | QRB ROS / IQ9 advantage |
| --- | --- | --- |
| Neural-network inference | CPU or generic GPU unless you wire QNN yourself | `qrb_ros_nn_inference` runs model artifacts through QNN / Hexagon HTP |
| Camera frame movement | `sensor_msgs::Image` payload copies between nodes | QRB transport can pass DMA-buf fds for hardware-to-hardware paths |
| Full perception pipeline | Manually wire camera, preprocess, inference, postprocess, topics | `qrb_ros_samples` gives accelerator-aware reference launch files |
| Evaluation path | Start from a blank ROS graph | Start from a working sample, then replace model/camera/postprocess as needed |

This workshop uses a USB camera for accessibility. Production IQ9 camera paths can move toward `qrb_ros_camera` and `qrb_ros_transport` for Qualcomm camera + DMA-buf workflows.

## Repository contents

```text
models/midas_yolo_combined_int8_split.bin   # included QNN context binary
scripts/setup_iq9_workshop.sh               # install ROS/QIRP/QRB ROS dependencies
scripts/prepare_demo_workspace.sh           # fetch PR #429, stage model, build sample
scripts/check_demo_prereqs.sh               # verify model, ROS package, launch args, camera nodes
scripts/run_usb_demo.sh                     # source the workspace and launch the USB-camera demo
```

No slide/runbook docs are included in this attendee repo.

## Requirements

- Qualcomm Dragonwing IQ-9075 EVK / IQ9.
- Ubuntu 24.04 / Qualcomm Ubuntu image.
- ROS 2 Jazzy apt repository access.
- Internet access for apt and GitHub during setup.
- USB camera plugged into the IQ9 before the live demo.

## Quick start

Clone the workshop repository on the IQ9:

```bash
cd /home/ubuntu/workshop
git clone <WORKSHOP_REPO_URL> iq9-midas-yolo-workshop
cd iq9-midas-yolo-workshop
```

Install dependencies:

```bash
./scripts/setup_iq9_workshop.sh
```

Prepare the QRB ROS sample workspace and build the demo package:

```bash
./scripts/prepare_demo_workspace.sh
```

Check readiness:

```bash
./scripts/check_demo_prereqs.sh
```

Run the USB-camera demo:

```bash
./scripts/run_usb_demo.sh
```

If the USB camera is not `/dev/video0`, pass the detected device:

```bash
./scripts/run_usb_demo.sh video_device:=/dev/video2
```

The helper script is equivalent to sourcing ROS, sourcing the built QRB ROS sample workspace, and running `ros2 launch sample_midas_yolo_parallel launch_with_usb_cam.py`.

## Inspect the running ROS graph

In a second terminal:

```bash
source /opt/ros/jazzy/setup.bash
source /home/ubuntu/workshop/qrb_ros_samples/install/local_setup.bash
ros2 topic list
ros2 topic hz /midas_yolo_overlay
```

Expected demo topics include:

- `/image_raw`
- `/midas_inference_input_tensor`
- `/yolo_seg_inference_input_tensor`
- `/midas_inference_output_tensor`
- `/yolo_seg_inference_output_tensor`
- `/midas_depth_map`
- `/midas_depth_gray`
- `/midas_yolo_overlay`

## Model artifact

The model is included in this repo:

```text
models/midas_yolo_combined_int8_split.bin
```

`prepare_demo_workspace.sh` copies it to the launch-file default:

```text
/opt/model/midas_yolo_combined_int8_split.bin
```

The binary contains two QNN graphs in one shared context:

| Graph | Purpose |
| --- | --- |
| `midas` | MiDaS depth estimation |
| `yolov11_seg` | YOLO11n segmentation |

## Troubleshooting

| Symptom | Check | Fix |
| --- | --- | --- |
| Package not found | `ros2 pkg prefix sample_midas_yolo_parallel` | Re-run `./scripts/prepare_demo_workspace.sh` |
| Model load fails | `ls -lh /opt/model/midas_yolo_combined_int8_split.bin` | Re-run prepare script; it stages the included model |
| No camera | `v4l2-ctl --list-devices` | Plug camera, then pass `video_device:=/dev/videoX` |
| No overlay topic | `ros2 topic list` | Confirm launch is still running and `/image_raw` exists |
| Low/no detections | Increase lighting, aim at common COCO-like objects, or adjust `score_thresh` |

## Upstream references

- Demo PR: https://github.com/qualcomm-qrb-ros/qrb_ros_samples/pull/429
- QRB ROS overview: https://dragonwingdocs.qualcomm.com/Ubuntu/robotics-workflows/qrb-ros-overview
- QRB ROS NN inference: https://dragonwingdocs.qualcomm.com/Ubuntu/robotics-workflows/qrb-ros-nn-inference
- QRB ROS transport: https://dragonwingdocs.qualcomm.com/Ubuntu/robotics-workflows/qrb-ros-transport
- QRB ROS samples: https://dragonwingdocs.qualcomm.com/Ubuntu/robotics-workflows/qrb-ros-samples
- IQ-9075 flash flow: https://dragonwingdocs.qualcomm.com/Ubuntu/devices/iq9075-evk/update-software/flash-using-qualcomm-launcher
- IQ-9075 required packages: https://dragonwingdocs.qualcomm.com/Ubuntu/devices/iq9075-evk/Install_required_software_packages
- ROS / robotics setup: https://dragonwingdocs.qualcomm.com/Ubuntu/robotics-workflows/software-setup
