import ast,json,tempfile,unittest
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]/'lab/p3-a02-cycle01.py'
def require(value,message):
 if not value:raise RuntimeError(message)
def functions():
 tree=ast.parse(SOURCE.read_text());tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
 return compile(tree,str(SOURCE),'exec')
class CycleStops(unittest.TestCase):
 def test_existing_cycle_refuses_before_any_hardware_operation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'cycle.json').write_text('{}')
   g={'prerequisite':lambda:None,'require':require,'D':root};exec(functions(),g);g['prerequisite']=lambda:None
   with self.assertRaisesRegex(RuntimeError,'cycle already attempted'):g['execute']()
 def test_failed_attempt_cannot_be_retried(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);latch=root/'FAILED';latch.write_text('{}')
   g={'FAIL':latch,'require':require};exec(functions(),g)
   with self.assertRaisesRegex(RuntimeError,'no retry'):g['prerequisite']()
 def test_missing_h5r2_acceptance_blocks_before_runtime_or_target(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);g={'FAIL':root/'P3_A02_FAILED.json','B':root,'require':require,'read':lambda p:{'result':'NOT_ACCEPTED'}};exec(functions(),g)
   with self.assertRaisesRegex(RuntimeError,'H5R2 acceptance missing'):g['prerequisite']()
if __name__=='__main__':unittest.main()
