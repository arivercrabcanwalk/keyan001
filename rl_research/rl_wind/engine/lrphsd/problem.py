"""Paper/official-data contract; input order and node IDs are preserved."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import math, hashlib, json

@dataclass(frozen=True)
class Parameters:
    speed: float = 900.0
    flight_energy: float = 0.018
    small_battery: float = 0.81
    large_battery: float = 1.0
    small_radius: float = 4000.0
    large_radius: float = 5000.0
    small_duration: float = 480.0
    large_duration: float = 600.0
    small_station_cost: float = 22.8
    large_station_cost: float = 30.4
    small_drone_cost: float = 5.0
    large_drone_cost: float = 8.0
    time_cost: float = 0.5
    def __post_init__(self):
        if not all(math.isfinite(v) and v >= 0 for v in asdict(self).values()):
            raise ValueError('parameters must be finite and nonnegative')
        if min(self.speed,self.small_battery,self.large_battery,self.small_duration,self.large_duration,self.small_radius,self.large_radius) <= 0:
            raise ValueError('physical capacities/speed/radii must be positive')
        if self.small_battery > self.large_battery or self.small_radius > self.large_radius or self.small_duration > self.large_duration:
            raise ValueError('small/large contract ordering')

@dataclass(frozen=True)
class Node:
    id: int
    x: float
    y: float
    energy: float
    service: float

@dataclass
class Instance:
    name: str
    targets: tuple
    stations: tuple
    sha256: str
    params: Parameters = field(default_factory=Parameters)
    def __post_init__(self):
        self.nodes = {n.id:n for n in self.targets+self.stations}
        self.target_ids = tuple(n.id for n in self.targets)
        self.dist = {(a.id,b.id):math.hypot(a.x-b.x,a.y-b.y) for a in self.nodes.values() for b in self.nodes.values()}
        self.gdist = self.dist  # [rl_wind] geometric distances (coverage); self.dist may be replaced by wind-effective distances
    def radius(self, kind): return self.params.small_radius if kind == 1 else self.params.large_radius
    def duration(self, kind): return self.params.small_duration if kind == 1 else self.params.large_duration
    def capacity(self, drone): return self.params.large_battery if drone == 0 else self.params.small_battery
    def fixed(self, kind):
        p=self.params
        return 0.0 if kind == 0 else (p.small_station_cost+p.small_drone_cost if kind == 1 else p.large_station_cost+p.large_drone_cost+p.small_drone_cost)

def read_instance(path, params=None):
    path=Path(path); raw=path.read_bytes(); rows=raw.decode('utf-8-sig').splitlines()
    if not rows or 'CUST_NO' not in rows[0]: raise ValueError('official header required')
    nodes=[]
    for lineno,line in enumerate(rows[1:],2):
        if not line.strip(): continue
        fields=line.split()
        if len(fields)!=5: raise ValueError(f'line {lineno}: expected five fields')
        number=float(fields[0]); vals=list(map(float,fields[1:]))
        if not number.is_integer() or not all(math.isfinite(v) for v in [number]+vals):raise ValueError('nonfinite/node ID')
        if min(vals[2:])<0:raise ValueError('negative service quantity')
        nodes.append(Node(int(number),*vals))
    if len({n.id for n in nodes})!=len(nodes):raise ValueError('duplicate node ID')
    targets=tuple(n for n in nodes if n.energy>0); stations=tuple(n for n in nodes if n.energy==0)
    if not targets or not stations:raise ValueError('targets/stations required')
    if any(n.service!=0 for n in stations):raise ValueError('station service must be zero under official contract')
    return Instance(path.stem,targets,stations,hashlib.sha256(raw).hexdigest(),params or Parameters())

def empty_solution(instance, types):
    return {'schema_version':1,'instance':instance.name,'instance_sha256':instance.sha256,'station_types':list(types),'routes':[[[],[]] for _ in instance.stations]}

def normalized(solution):
    out=json.loads(json.dumps(solution))
    for station in out['routes']:
        for d in range(2):station[d]=[trip for trip in station[d] if trip]
    return out
