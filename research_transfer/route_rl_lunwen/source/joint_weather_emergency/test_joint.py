import unittest,dataclasses,math
from emergency_scenario import *
from joint_core import *
class Tests(unittest.TestCase):
 def tiny(self):
  return Scenario('joint-unit',(Station(0,0.,0.),),(Task(1,0,900.,0.,.2,2.),Task(100000,0,-500.,0.,.05,2.,1.,16.,10,True)),(0,0),(1.,.81),Trace(((800.,180.,0.),)),EmergencyConfig(horizon=720.,duty_limit=480.),(180.,0.))
 def test_independent_physics_and_all_controls(self):
  for name in ('nearest','deadline','prior','mix0.5','mix1','mix2'):
   s=self.tiny();m,r=execute(s,RoutePolicy(context(s),180.,name));self.assertTrue(m['replay_verified'],m);self.assertTrue(m['complete_return'],m);self.assertEqual(m['invalid_actions'],0)
 def test_mask_does_not_read_future(self):
  s=self.tiny();o=EmergencySimulator(s).observation(0);a,f,p=feature_actions(o,context(s),180.)
  s2=dataclasses.replace(s,trace=Trace(((.5,180.,0.),(800.,-180.,0.))))
  self.assertEqual(feature_actions(EmergencySimulator(s2).observation(0),context(s2),180.),(a,f,p))
 def test_network_outputs_physical_actions(self):
  s=self.tiny();p=RoutePolicy(context(s),180.,'model',ResidualActor());m,r=execute(s,p)
  self.assertTrue(m['replay_verified'],m);self.assertTrue(all(a['action']['kind'] in ('TARGET','RETURN','WAIT') for a in r['actions'] if 'action' in a))
 def test_failure_not_rewarded(self):
  s=self.tiny();m,r=execute(s,lambda o:Action.wait(5.) if o.own.at_station else Action.return_to_station());self.assertGreater(m['J'],10000.)
 def test_tamper_rejected(self):
  s=self.tiny();m,r=execute(s,RoutePolicy(context(s),180.,'prior'));r['incurred_cost']+=1.;self.assertFalse(verify_result(snapshot(s),r)['verified'])
 def test_author_adapter_shared_checker(self):
  s=self.tiny()
  for name in ('author_insert','author_dispatch'):
   m,r=execute(s,AuthorRoutePolicy(context(s),180.,{0:[[1]],1:[]},name));self.assertTrue(m['replay_verified'],m)
if __name__=='__main__':unittest.main(verbosity=2)
