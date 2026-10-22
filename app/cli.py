"""Video metadata and local Pose2D command line interface."""

import argparse
import json
import sys
from pathlib import Path

from core.video.decoder import VideoInputError, inspect_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a local MP4 or generate a Pose2D overlay.")
    parser.add_argument("video", help="Local MP4 file path")
    parser.add_argument("--json", action="store_true", help="Print metadata or processing report as JSON")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--pose2d", action="store_true", help="Generate 2D pose overlay and keypoints")
    operation.add_argument("--pose3d", action="store_true", help="Generate local MediaPipe 3D pose and preview")
    parser.add_argument("--list-targets", action="store_true", help="List first-frame people (add --pose3d for M2 candidates)")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--target-index", type=int, help="First-frame candidate index (0-based)")
    selection.add_argument("--target-box", nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"),
                           help="Select a first-frame person using a pixel-space rectangle")
    parser.add_argument("--output", type=Path, help="New output directory (required with --pose2d)")
    parser.add_argument("--preview-output", type=Path,
                        help="Save a numbered first-frame PNG/JPG with --list-targets (no overwrite)")
    parser.add_argument("--model-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "models" / "pose2d")
    parser.add_argument("--pose3d-model-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "models" / "pose3d")
    parser.add_argument("--max-people", type=int, choices=range(1, 5), default=4,
                        help="M2 candidate capacity; 1 asserts the input contains only one person")
    args = parser.parse_args(argv)
    if args.pose2d and args.list_targets:
        parser.error("--pose2d and --list-targets cannot be combined")
    if (args.pose2d or args.pose3d) and not args.list_targets and args.output is None:
        parser.error("--pose2d / --pose3d requires --output")
    if args.output is not None and (not (args.pose2d or args.pose3d) or args.list_targets):
        parser.error("--output requires --pose2d or --pose3d processing")
    if (args.target_index is not None or args.target_box is not None) and \
            (not (args.pose2d or args.pose3d) or args.list_targets):
        parser.error("--target-index and --target-box require --pose2d or --pose3d processing")
    if args.target_index is not None and args.target_index < 0:
        parser.error("--target-index must be non-negative")
    if args.preview_output is not None and not args.list_targets:
        parser.error("--preview-output requires --list-targets")
    if args.pose3d:
        from app.cli3d import run_pose3d
        return run_pose3d(args)
    if args.pose2d or args.list_targets:
        from core.pose2d.interface import Pose2DError
        from core.pose2d.rtmpose_backend import RTMPoseBackend
        from app.processing import process_pose2d

        backend = None
        try:
            metadata = inspect_video(args.video)
            if args.output is not None and args.output.exists():
                raise Pose2DError("Output directory already exists. Choose a new directory.")
            print("Loading local pose models...", file=sys.stderr)
            backend = RTMPoseBackend(args.model_dir, target_index=args.target_index,
                                     target_box=args.target_box)
            if args.list_targets:
                import cv2
                capture = cv2.VideoCapture()
                try:
                    if not capture.open(str(Path(args.video).resolve()), cv2.CAP_FFMPEG,
                                        [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                         cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]):
                        raise VideoInputError("Cannot open first frame.")
                    ok, frame = capture.read()
                    if not ok:
                        raise VideoInputError("Cannot decode first frame.")
                    candidates = backend.detect(frame)
                    if args.preview_output is not None:
                        preview = args.preview_output
                        if str(preview).startswith(("\\\\", "//")) or "://" in str(preview) or \
                                preview.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                            raise Pose2DError("Preview must be a local PNG or JPG file.")
                        if preview.is_symlink() or any(p.is_symlink() for p in preview.parents):
                            raise Pose2DError("Preview symbolic links are not supported.")
                        for index, box in enumerate(candidates):
                            x1, y1, x2, y2 = (int(v) for v in box)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 3)
                            cv2.putText(frame, f"TARGET {index}", (x1, max(25, y1 - 8)),
                                        cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 220, 255), 2, cv2.LINE_AA)
                        encoded, image = cv2.imencode(preview.suffix.lower(), frame)
                        if not encoded:
                            raise Pose2DError("Cannot encode target preview.")
                        try:
                            preview.parent.mkdir(parents=True, exist_ok=True)
                            with preview.open("xb") as stream:
                                stream.write(image.tobytes())
                        except OSError as exc:
                            raise Pose2DError("Cannot save preview; choose a new, writable filename.") from exc
                except cv2.error as exc:
                    raise VideoInputError("Cannot decode the first frame for target selection.") from exc
                finally:
                    capture.release()
                print(json.dumps({"width": metadata.width, "height": metadata.height,
                                  "candidates": [{"index": i, "bbox": [float(v) for v in box]}
                                                 for i, box in enumerate(candidates)]}, indent=2))
                return 0
            report = process_pose2d(
                args.video, args.output, backend,
                progress=lambda done, total: print(f"Processing: {done}/{total}", file=sys.stderr),
            )
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"Completed: {report['frames_processed']} frames")
                print(f"Target tracked: {report['frames_with_target']} frames")
                print(f"Output: {args.output}")
            if report["multi_person_frames"]:
                print("Warning: multiple people detected; only the selected target is associated.", file=sys.stderr)
            if report["frames_without_person"]:
                print("Warning: target unavailable in some frames; inspect tracking.json for the reason.", file=sys.stderr)
            if report["frames_requiring_reselection"]:
                print("Warning: target identity became uncertain or lost. Reselection is required; "
                      "no automatic person replacement was attempted.", file=sys.stderr)
            if report["frames_with_target"] < report["frames_processed"] * .5:
                print("Warning: fewer than half of the frames have a usable target pose. "
                      "This output needs review; check the numbered target preview and tracking.json.",
                      file=sys.stderr)
            if any(report["joint_issue_frame_counts"].values()):
                print("Warning: some joints are low-confidence or invalid. "
                      "Joint visibility reasons are recorded in tracking.json.", file=sys.stderr)
            if not report["frame_count_matches_metadata"]:
                print("Warning: decoded frame count differs from metadata. See report.json; "
                      "container estimates and decode errors cannot be distinguished by EOF alone.",
                      file=sys.stderr)
            return 0
        except (VideoInputError, Pose2DError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("Cancelled. Partial results, if any, are marked cancelled in report.json.", file=sys.stderr)
            return 130
        finally:
            if backend is not None:
                backend.close()
    try:
        metadata = inspect_video(args.video)
    except VideoInputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    if args.json:
        print(json.dumps(metadata.to_dict(), allow_nan=False, indent=2))
    else:
        print(f"Resolution: {metadata.width} x {metadata.height}")
        print(f"FPS: {metadata.fps:.3f}")
        print(f"Frames: {metadata.frame_count}")
        print(f"Duration (estimate): {metadata.duration_seconds_estimate:.3f} seconds")
        print(f"Size: {metadata.size_bytes} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
