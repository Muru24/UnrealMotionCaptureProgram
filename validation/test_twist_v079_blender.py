"""Run inside Blender: geometry properties of twist-only correction and gap accounting."""
import importlib.util,math,json,sys,unittest
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('solver',ROOT/'tools/animate_reference_rig.py')
solver=importlib.util.module_from_spec(spec);spec.loader.exec_module(solver)

class TwistTests(unittest.TestCase):
    def test_identity(self):
        m=Matrix.Identity(3);r,step=solver.follow_parent_twist(m,m,30)
        self.assertLess(sum((r[i]-m[i]).length for i in range(3)),1e-6);self.assertEqual(step,0)

    def test_swing_not_limited_even_at_180(self):
        for direction in (Vector((1,0,0)),Vector((0,-1,0)),Vector((.01,-1,.01))):
            m=solver.transport_roll(Matrix.Identity(3),direction)
            self.assertLess((m.col[1]-direction.normalized()).length,1e-5)
            r,step=solver.follow_parent_twist(m,solver.transport_roll(Matrix.Identity(3),direction),30)
            self.assertLess((r.col[1]-direction.normalized()).length,1e-5)

    def test_rate_and_orthogonality(self):
        anchor=Quaternion(Vector((0,1,0)),math.radians(170)).to_matrix()
        for fps in (24,30,60,120):
            r,step=solver.follow_parent_twist(Matrix.Identity(3),anchor,fps)
            self.assertLessEqual(abs(math.degrees(step)),120/fps+1e-6)
            self.assertLess((r.col[1]-Vector((0,1,0))).length,1e-5)
            self.assertAlmostEqual(r.determinant(),1,places=5)

    def test_converges_to_parent_prior(self):
        r=Matrix.Identity(3);anchor=Quaternion(Vector((0,1,0)),math.radians(90)).to_matrix()
        for _ in range(90):r,_=solver.follow_parent_twist(r,anchor,30)
        self.assertLess(r.to_quaternion().rotation_difference(anchor.to_quaternion()).angle,.002)

    def test_fps_equivalence(self):
        values=[];anchor=Quaternion(Vector((0,1,0)),.8).to_matrix()
        for fps in (30,60):
            r=Matrix.Identity(3)
            for _ in range(fps):r,_=solver.follow_parent_twist(r,anchor,fps)
            values.append(r.to_quaternion())
        self.assertLess(values[0].rotation_difference(values[1]).angle,.002)

    def test_shortest_axial_path(self):
        a=Quaternion(Vector((0,1,0)),math.radians(179)).to_matrix()
        b=Quaternion(Vector((0,1,0)),math.radians(-179)).to_matrix()
        _,step=solver.follow_parent_twist(a,b,30)
        self.assertGreater(step,0);self.assertLess(math.degrees(step),2)

    def test_gap_report_does_not_bridge_scene(self):
        rows=[{'bone_status':['missing'],'tracking_segment':0,'scene_index':int(i>=8)} for i in range(20)]
        spans=solver.missing_spans(rows,['arm'],30)
        self.assertEqual([(s['start_frame'],s['end_frame']) for s in spans],[(0,7),(8,19)])
        self.assertTrue(all(s['kind']=='long_missing' and not s['filled'] for s in spans))

    def test_short_and_trailing_gaps(self):
        rows=[{'bone_status':['missing' if i in (1,2,5) else 'solved'],'tracking_segment':0,'scene_index':0} for i in range(6)]
        spans=solver.missing_spans(rows,['arm'],30)
        self.assertEqual([(s['start_frame'],s['end_frame'],s['kind']) for s in spans],[(1,2,'short_missing'),(5,5,'short_missing')])

result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TwistTests))
out=Path(sys.argv[sys.argv.index('--')+1]);out.write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun}),encoding='utf-8')
if not result.wasSuccessful():raise RuntimeError('Twist property tests failed')
