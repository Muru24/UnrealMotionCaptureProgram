"""M2 CLI operations, imported only when explicitly requested."""

import json
from pathlib import Path
import sys

import cv2

from app.processing3d import process_pose3d
from core.pose2d.interface import Pose2DError
from core.pose3d.interface import Pose3DError
from core.pose3d.mediapipe_backend import MediaPipeBackend
from core.video.decoder import VideoInputError, inspect_video


def run_pose3d(args):
    backend = None
    try:
        metadata = inspect_video(args.video)
        if args.output is not None and args.output.exists():
            raise Pose3DError('Output directory already exists. Choose a new directory.')
        print('Loading local MediaPipe Full CPU model...', file=sys.stderr)
        backend = MediaPipeBackend(args.pose3d_model_dir, args.target_index, args.target_box, args.max_people)
        if args.max_people == 1:
            print('Single-person input mode: do not use for multi-person or mirror-person scenes.', file=sys.stderr)
        if args.list_targets:
            capture = cv2.VideoCapture()
            try:
                if not capture.open(str(Path(args.video).resolve()), cv2.CAP_FFMPEG,
                                    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                     cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]):
                    raise VideoInputError('Cannot open first frame.')
                ok, frame = capture.read()
                if not ok:
                    raise VideoInputError('Cannot decode first frame.')
                boxes = backend.detect(frame)
            finally:
                capture.release()
            if args.preview_output is not None:
                path = args.preview_output
                if str(path).startswith(('\\\\', '//')) or '://' in str(path) or \
                        path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                    raise Pose3DError('Preview must be a local PNG or JPG file.')
                if path.is_symlink() or any(p.is_symlink() for p in path.parents):
                    raise Pose3DError('Preview symbolic links are not supported.')
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 2)
                    cv2.putText(frame, f'M2 TARGET {i}', (x1, max(25, y1-8)),
                                cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 220, 255), 2)
                ok, image = cv2.imencode(path.suffix, frame)
                if not ok:
                    raise Pose3DError('Cannot encode candidate preview.')
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream:
                    stream.write(image.tobytes())
            print(json.dumps({'backend': backend.name, 'width': metadata.width,
                              'height': metadata.height,
                              'candidates': [{'index': i, 'bbox': b.tolist()} for i,b in enumerate(boxes)]},
                             indent=2))
            return 0
        report = process_pose3d(args.video, args.output, backend,
                                progress=lambda done, total: print(f'Processing 3D: {done}/{total}',
                                                                   file=sys.stderr))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Completed: {report['frames_processed']} frames")
            print(f"Target tracked: {report['frames_with_target']} frames")
            print(f"Valid torso: {report['frames_with_valid_torso']} frames (not an accuracy score)")
            print(f'Output: {args.output}')
        for warning in report['warnings']:
            print('Warning: '+warning, file=sys.stderr)
        if report['frames_with_target'] < report['frames_processed']*.5:
            print('Warning: target pose is unavailable in more than half of the frames. '
                  'Do not treat this output as a successful motion reconstruction.', file=sys.stderr)
        print('3D is hip-relative; inspect preview3d.mp4 before using the result.', file=sys.stderr)
        return 0
    except (Pose3DError, Pose2DError, VideoInputError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except (OSError, cv2.error):
        print('Error: Cannot read or write local M2 files; choose a new writable output.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelled. Partial outputs are marked cancelled in report.json.', file=sys.stderr)
        return 130
    finally:
        if backend is not None:
            backend.close()
