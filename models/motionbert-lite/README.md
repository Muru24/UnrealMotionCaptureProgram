# MotionBERT-Lite comparison asset

Official repository: https://huggingface.co/walterzhu/MotionBERT
Pinned revision: 370a9196aa3c89198b134c82476143b01c0fb32c
Checkpoint: checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin
Repository LICENSE: Apache-2.0 (local LICENSE retained).
Source adapter uses original DSTformer.py/drop.py and matching config in .validation/motionbert/source. Manifest records every upstream asset SHA256. No external runtime fetch.

Run app.independent_pose_job with the existing RTMPose model and isolated SAM3D Torch runtime. This is a separate experimental H36M17 output. COCO head uses an explicit eye-midpoint proxy. Do not interpret model score as true visibility or normalized 3D as meters/MHR70/UE rotations. See validation/sam2/independent-v0521 and md/CURRENT_TASK.md.
