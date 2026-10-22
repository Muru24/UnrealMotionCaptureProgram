"""Offline MotionBERT-Lite child; strict weights and separate H36M output."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.validation/motionbert/source')]


def main(out):
    import torch,numpy as np
    from app.fullbody_job import write
    from core.pose3d.motionbert_adapter import flip_h36m,H36M_NAMES
    manifest=json.loads((ROOT/'models/motionbert-lite/manifest.json').read_text(encoding='utf-8'))
    for record in manifest['files']:
        path=(ROOT/record['path']).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('MotionBERT asset hash differs.')
    from lib.model.DSTformer import DSTformer
    if not torch.cuda.is_available():raise RuntimeError('This comparison worker requires CUDA.')
    torch.set_num_threads(8);torch.manual_seed(0)
    model=DSTformer(dim_feat=256,dim_rep=512,depth=5,num_heads=8,mlp_ratio=4,maxlen=243,num_joints=17,att_fuse=True)
    checkpoint=torch.load(ROOT/'models/motionbert-lite/best_epoch.bin',map_location='cpu',weights_only=True)
    state={key.removeprefix('module.'):value for key,value in checkpoint['model_pos'].items()}
    model.load_state_dict(state,strict=True);model=model.cuda().eval()
    request=json.loads((out/'motionbert-request.json').read_text(encoding='utf-8'));result=[]
    with torch.inference_mode():
        for k,segment in enumerate(request['segments']):
            array=np.asarray(segment['input'],np.float32)
            if array.ndim!=3 or array.shape[1:]!=(17,3) or not 1<=len(array)<=243 or not np.isfinite(array).all():raise ValueError('Invalid MotionBERT input.')
            if len(segment['indices'])!=len(array) or any(b!=a+1 for a,b in zip(segment['indices'],segment['indices'][1:])):raise ValueError('Invalid MotionBERT segment order.')
            x=torch.from_numpy(array[None]).cuda();flipped=torch.from_numpy(flip_h36m(array)[None]).cuda()
            q=(model(x).cpu().numpy()[0]+flip_h36m(model(flipped).cpu().numpy()[0]))/2
            if q.shape!=array.shape or not np.isfinite(q).all():raise ValueError('Invalid MotionBERT output.')
            q[0,0,2]=0 # Official global-lite inference convention, not metric root motion.
            norm=segment['normalization'];xy=q[...,:2]*norm['scale']/2+np.asarray(norm['center'])
            xy=xy*(min(request['video']['width'],request['video']['height'])/2)+np.array([request['video']['width'],request['video']['height']])/2
            result.extend({'frame_index':i,'world_joints_normalized':pose.tolist(),'image_xy_proxy':pixels.tolist()} for i,pose,pixels in zip(segment['indices'],q,xy))
            write(out/'motionbert-progress.json',{'done':k+1,'total':len(request['segments'])})
    write(out/'motionbert-joints.json',{'schema':'motionbert_h36m17_normalized_v1','joint_names':H36M_NAMES,'frames':result,'model_revision':manifest['revision'],
        'checkpoint_strict':True,'weights_only_load':True,'coordinates':'uncalibrated_model_normalized_not_metric_not_MHR',
        'native_MHR_rotations_modified':False})


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
