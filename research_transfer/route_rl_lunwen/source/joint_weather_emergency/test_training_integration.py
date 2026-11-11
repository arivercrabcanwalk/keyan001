"""<EXPERIMENT_SERVER> BC -> physical rollout -> registered RL optimizer integration."""
import unittest,random,torch
from run_development import warm_start,optimize_group
from joint_core import *
from test_joint import Tests
class Integration(unittest.TestCase):
 def test_actual_bc_and_registered_rl_update(self):
  torch.set_num_threads(1);torch.manual_seed(9905);s=Tests().tiny();c=context(s)
  teacher=RoutePolicy(c,180.,'prior',teacher=RoutePolicy(c,180.,'nearest'))
  metrics,result=execute(s,teacher);self.assertTrue(metrics['replay_verified'])
  model=ResidualActor();opt=torch.optim.Adam(model.parameters(),lr=1e-3)
  before={k:v.detach().clone() for k,v in model.state_dict().items()}
  stats=warm_start(model,opt,teacher.demonstrations,9905,60.)
  self.assertGreater(stats['updates'],0);self.assertTrue(any(not torch.equal(before[k],v) for k,v in model.state_dict().items()))
  episodes=[];costs=[]
  for sample in range(4):
   policy=RoutePolicy(c,180.,'model',model,True);m,r=execute(s,policy)
   self.assertTrue(m['replay_verified']);self.assertTrue(m['complete_return']);self.assertEqual(m['invalid_actions'],0)
   episodes.append(policy.transitions);costs.append(m['J'])
  middle={k:v.detach().clone() for k,v in model.state_dict().items()}
  loss=optimize_group(model,opt,episodes,costs);self.assertTrue(torch.isfinite(loss));self.assertTrue(any(not torch.equal(middle[k],v) for k,v in model.state_dict().items()))
  self.assertTrue(all(torch.isfinite(v).all() for v in model.state_dict().values()))
  print('BC_RL_INTEGRATION_PASS',stats['updates'],len(episodes))
if __name__=='__main__':unittest.main(verbosity=2)
