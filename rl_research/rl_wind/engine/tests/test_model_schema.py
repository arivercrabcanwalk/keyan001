
import sys,tempfile
from pathlib import Path
import torch
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r))
from carl.ppo import PolicyNet,save_model,load_model,MODEL_SCHEMA
from carl.state import STATE_SCHEMA,ACTION_SCHEMA,REWARD_SCHEMA

with tempfile.TemporaryDirectory() as d:
    p=Path(d)/"valid.pt";m=PolicyNet();save_model(m,p);load_model(p)
    wrong=Path(d)/"wrong_model.pt"
    torch.save({"state_dict":m.state_dict(),"model_schema":"wrong",
                "state_schema":STATE_SCHEMA,"action_schema":ACTION_SCHEMA,
                "reward_schema":REWARD_SCHEMA},wrong)
    try:load_model(wrong)
    except ValueError:pass
    else:raise AssertionError("wrong model architecture schema accepted")
    legacy=Path(d)/"legacy.pt";torch.save(m.state_dict(),legacy)
    try:load_model(legacy)
    except ValueError:pass
    else:raise AssertionError("legacy checkpoint accepted")
print("PASS model_schema")
