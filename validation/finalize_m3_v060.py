"""Freeze MVP3 code/assets and evidence, leaving earlier MVPs recoverable."""
from pathlib import Path
import json,hashlib,re,zipfile
root=Path(__file__).resolve().parents[1];e=root/'validation/m3'
rig=json.loads((e/'rig-roundtrip.json').read_text(encoding='utf-8'))
cases=json.loads((e/'real-conversions.json').read_text(encoding='utf-8'))
gui=json.loads((e/'gui-tests.json').read_text(encoding='utf-8'))
assert len(rig['results'])==3 and all(r['bones']==22 and r['max_head_error_m']<1e-4 for r in rig['results'])
assert sum(c['frames'] for c in cases)==6051 and all(c['inputs_unchanged'] for c in cases)
assert len(gui)==8 and all(c['exit']==0 for c in gui)
n=max(int(p.name[4:]) for p in (root/'진행상황').iterdir() if p.is_dir() and re.fullmatch(r'case\d+',p.name))+1
case=root/'진행상황'/f'case{n}';case.mkdir()
common=('사용자 승인 M3: Blender제작 참조본을 Unreal/Unity 양쪽 임포트 대상으로 제공하고 '
        '영상 옆에 동기화된 표준스켈레톤을 표시한다. v0.6.0, 원시MHR70·회전·MVP2결과 보존. '
        '본회전/메쉬모션/Bake/엔진직접임포트는 미구현·미검증으로 구분한다. '
        '새모델/의존성/다운로드/GPU재추론 없음.\n')
texts={
'CURRENT_TASK.md':('Milestone M3 Motion Skeleton / 구현 및 이번 검증 완료, 사용자 시각 확인 대기. '
 'Goal: 엔진중립22본 T-pose 리그·MotionJSON·영상 옆 3D패널. '
 'Scope: core/motion, app/motion_job.py/skeleton_panel.py/gui.py, assets/skeletons, '
 'tools/build_reference_rig.py, tests/test_motion_skeleton.py, md/MOTION_FORMAT.md. '
 'Acceptance: 계층/길이/축/누락·출처 보존, 자동/기존결과CPU변환, 재생·seek 동기화, Blender/FBX계층·스킨검사.\n'
 '확인방법: StartPrototype.cmd 재실행→새SAM출력(자동변환) 또는 결과목록에서기존영상→오른쪽3D패널 변환. '
 '정면/측면·드래그회전·휠확대. LongSword/프로미스나인/유니 기존결과에 motion/motion.json 생성 완료. '
 '소스는 LongSword재관측연결, 나머지2개는완료된후처리없어raw이며패널에출처표시. '
 '표본/구간영상은길이불일치시동기표시안함. 다음M4는로컬본Quaternion·본메쉬모션 연결.\n'),
'PROGRESS.md':('구현: MotionHumanoid22(root+21deform) 공통정의·Blender정지리그와강체스킨본프록시메쉬, '
 'Unity(-Z/Y)·Unreal(X/Z) FBX와정적Unity역할표생성. 설치된Blender5.1.1 background/factory-startup으로 '
 '제작해사용자Blender창/장면은조작하지않았다.\n'
 'MHR70의정확한이름·순서를검사하고카메라(x,y,z)→Blender(x,z,-y) 우수좌표계변환, '
 '골반상대·고정참조길이로22본관절을구성. 척추/쇄골/머리/발끝파생점·제자리root·누락을명시, '
 '원래카메라골반위치와mapped위치도보존. 보정된관절을native회전으로간주하지않음. '
 '재관측→부위→선택→raw 우선순위와SHA/정의hash/취소·캐시검사, 변환실패시원시출력유지.\n'
 'GUI는기존결과패널을유지한채영상/3D패널을나란히배치, 영상프레임과같은번호로재생·seek, '
 '표본길이불일치보류/데이터없는프레임빈표시, 회전·확대·기존결과CPU변환추가. '
 '출력과SAM결과열기에서자동변환.\n'
 '검증66고유PASS/권한opt-in1SKIP: 비GUI48+분리GUI8+기존GUI10, 모두최종exit0. '
 '신규12(코어10/GUI2)는참조부모/역할·길이/축·부호/입력불변/카메라이동제거/누락·NaN/출처/스키마·시간/취소·캐시·provenance/동기화·자동변환검사. '
 'compileallPASS. Blender3자산재임포트22본·스킨·최대head오차2.64e-7m미만. '
 '실제기존3영상6051프레임CPU변환(445/4272/1334), 원시/request/report SHA불변. '
 'pose존재445/2158/1252는입력가용수이지정확도아님. LongSword100 위치비교사진시각확인. '
 'Unity/UE 직접임포트와실제엔진애니메이션은검증하지않았다.\n'),
'ISSUES.md':('M3-AXIS-001 HANDLED: native카메라좌표를그대로Zup으로그리면축/뒤집힘오류위험. '
 '행렬(x,z,-y)와좌우이름/행렬행렬식+1·참조길이회귀검증. '
 'M3-PROVENANCE-001 HANDLED: raw와보정관절/그리기출처혼동방지위해입력단계·변경부위·SHA를JSON/패널에표시. '
 '실제2개영상은rawfallback임을명시한다.\n'
 'M3-ROOT-001 KNOWN_LIMIT: 골반고정높이/제자리루트/고정1.8m참조체형, '
 '실제사람신장·전역이동·골반상하·접지복원아님. '
 'M3-RIG-001 VERIFYING_ENGINE: FBX7.4두파일은Blender재임포트통과, '
 'UE/Unity 직접임포트·Avatar판정·버전호환은미검증. 임의Skeleton자동mapping이나UEMannequin동일리그아님. '
 'M3-MESH-001: 메쉬는126vertex강체본프록시, 완성형스킨캐릭터아니며아직동작키프레임없음.\n'
 'M2후등장후처리별도한계발견: candidate_job의초기26프레임기준자세의존은그이후첫등장입력에서후보단계를실패시킬수있다. '
 '이번은M3범위라M2추론을수정/재실행하지않고현재완료raw를입력으로표시해변환, '
 '원시추출·후처리완료와M3변환완료를구분한다. '
 'Norma의상가림/지속관절오류는미해결보류유지.\n'
 'QA-002 VERIFYING 재관측: 자동GUI2개결합중Tk __del__/worker JSON읽기와함께0xc0000008종료. '
 '개별프로세스재실행전부exit0확인, 원인해결로선언하지않는다. '
 'Blender생성중샌드박스밖.thumbnail캐시쓰기실패는비차단으로관측, '
 '주.blend/FBX생성·재임포트는별도통과. 원인불명수정이나사용자파일삭제없음.\n'),
'PROJECT.md':('사용자2026-10-21승인: M3에Blender제작 공통휴머노이드와Unreal/Unity용FBX자산, '
 '결과영상옆3D스켈레톤을포함. 현재22본정의assets/skeletons/humanoid_v1.json 및 '
 '새stable경계standard_motion_positions_v1를md/MOTION_FORMAT.md에정의했다. '
 '기존M2JSON포맷/모델출력은변경하지않고새motion하위파일로저장. '
 'Unity는이번참조리그/정적역할표대상이며Unity Animator Clip생성/엔진어댑터전체완료를뜻하지않는다. '
 'M3는관절위치/계층까지, M4로컬회전→M5엔진미리보기→후속Retarget/Bake순서유지. '
 '기존MVP2와Norma회귀보류상태유지.\n')}
for name,text in texts.items():
 p=root/'md'/name
 p.write_text('## 2026-10-21 / MVP3 v0.6.0 표준 스켈레톤·Blender 참조 리그\n\n'+text+common+
              f'4MD/{case.name} 동일SHA 보관/v0.6.0 MVP 저장.\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
 data=p.read_bytes();(case/name).write_bytes(data)
 assert hashlib.sha256(data).digest()==hashlib.sha256((case/name).read_bytes()).digest()
summary=root/'MVP요약/MVP3_표준스켈레톤_구현요약.md'
summary.write_text('# MVP3 v0.6.0 구현 요약\n\n'+common+'\n## 사용\n\n'
 '프로그램 재실행 후 새SAM출력은자동변환. 기존결과는목록에서영상을연뒤3D패널의변환을누른다. '
 '영상옆3D를재생/seek하며드래그회전·휠확대·정면/측면확인. '
 '기존LongSword/프로미스나인/유니3D결과는CPU변환을미리실행했다.\n\n'
 '## 산출물\n\n'
 '- [Blender 원본](../assets/skeletons/MotionHumanoid22.blend)\n'
 '- [Unity FBX](../assets/skeletons/MotionHumanoid22_Unity.fbx)\n'
 '- [Unreal FBX](../assets/skeletons/MotionHumanoid22_Unreal.fbx)\n'
 '- [자산 사용·임포트 검증 범위](../assets/skeletons/README.md)\n'
 '- [Motion JSON 규격](../md/MOTION_FORMAT.md)\n'
 '- 결과별 motion/motion.json과motion/report.json\n\n'
 '## 검증\n\n66PASS/권한opt-in1SKIP, compileallPASS. 새시험12개. '
 'Blender원본/FBX2개22본·부모·스킨·미터좌표재임포트검사. '
 '기존3영상6051프레임원시불변CPU변환. 입력모델의가용프레임을그대로유지했으며가림정답복원아님. '
 '처리시간은재사용/파일읽기를포함한CPU변환시간이지GPU추론속도아님.\n\n'
 '## 남은 일\n\n'
 '- Unreal/Unity 실제임포트·Humanoid Avatar판정 미검증.\n'
 '- 현재는제자리·고정체형관절위치, 본회전/스킨메쉬애니메이션/Root Motion/접지는후속단계.\n'
 '- Norma 의상오추정과기존M2후보초기26프레임기준제약, QA-002는남음.\n'
 '- 다음M4에서Quaternion로컬본회전과참조리그동작을연결한다.\n',encoding='utf-8')
p=root/'README.md';p.write_text('# MVP3 v0.6.0 · 표준 스켈레톤\n\n'
 '결과 영상 옆에 표준 22본 3D 미리보기가 추가됐습니다. 새 SAM 출력은 자동 변환되고, '
 '기존 결과는 3D 패널의 **변환**으로 준비합니다. 드래그 회전·휠 확대·정면/측면·재생바 동기화를 지원합니다. '
 '프로그램을 재실행하세요. Blender 원본/Unity·Unreal용 정지 FBX는 assets/skeletons에 있습니다. '
 '실제 엔진 임포트와 본 회전 애니메이션은 아직 검증·구현하지 않았습니다.\n\n'
 '[MVP3 요약](MVP요약/MVP3_표준스켈레톤_구현요약.md) · [자산 안내](assets/skeletons/README.md) · '
 '[Motion 규격](md/MOTION_FORMAT.md)\n\n---\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
p=root/'HOME_TRANSFER.md';p.write_text('# 최신 MVP3 v0.6.0\n\n'+common+
 'assets/skeletons의Blender·두FBX·공통정의와core/motion·GUI패널을함께보존한다. '
 '동작영상은기존outputs를사용하며새GPU환경설치불필요. '+case.name+'와MVP3요약참조.\n\n---\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
verification={'version':'0.6.0','unique_tests_passed':66,'skipped':1,'new_tests':12,
 'non_gui_tests':48,'isolated_gui_tests':8,'baseline_gui_tests':10,'compileall':'PASS',
 'rig_roundtrip':rig,'conversions':cases,'md_archive':case.name,'model_inference_executed':False,
 'unity_import_tested':False,'unreal_import_tested':False,'bone_rotations_generated':False,
 'three_pass_review':['right-handed axis/left-right/fixed lengths and missing states',
 'new versioned boundary and shared rig definition; raw and native rotations preserved',
 'sidecar provenance/atomic publish/cancellation/cache/output containment and UI timeline isolation']}
(e/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
folder=root/'snapshots/v0.6.0 MVP';folder.mkdir();target=folder/'m3-standard-motion-skeleton-v0.6.0.zip'
extra=[*[p for d in ('core/motion','assets/skeletons','MVP요약') for p in (root/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts],
       root/'app/motion_job.py',root/'app/skeleton_panel.py',root/'tools/build_reference_rig.py',
       root/'tests/test_motion_skeleton.py',root/'md/MOTION_FORMAT.md',Path(__file__),
       root/'validation/verify_reference_rig.py',*case.glob('*.md'),*[p for p in e.iterdir() if p.is_file()]]
# Only evidence directly under validation/m3 belongs in this snapshot, not pytest temp trees.
extra=[p for p in extra if p.is_file() and '__pycache__' not in p.parts]
with zipfile.ZipFile(root/'snapshots/v0.5.24 MVP/m2-delayed-target-start-v0.5.24.zip') as old,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as out:
 names=set()
 for info in old.infolist():
  name=info.filename
  if '__pycache__' in name or name.endswith('.pyc'):continue
  p=root/name;out.writestr(name,p.read_bytes() if not name.startswith('진행상황/') and p.is_file() else old.read(info));names.add(name)
 for p in extra:
  name=p.relative_to(root).as_posix()
  if name not in names:out.write(p,name);names.add(name)
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for name in ('app/gui.py','app/motion_job.py','app/skeleton_panel.py','core/motion/skeleton.py',
              'assets/skeletons/humanoid_v1.json','assets/skeletons/MotionHumanoid22.blend',
              'assets/skeletons/MotionHumanoid22_Unity.fbx','assets/skeletons/MotionHumanoid22_Unreal.fbx',
              'tests/test_motion_skeleton.py','md/MOTION_FORMAT.md'):
  assert z.read(name)==(root/name).read_bytes()
 count=len(z.infolist())
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
meta={'version':'0.6.0','files':count,'bytes':target.stat().st_size,'sha256':sha,'md_archive':case.name,
      'm3_user_review_pending':True,'m4_rotations':False,'unity_import_verified':False,'unreal_import_verified':False}
(folder/'snapshot.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta),flush=True)
