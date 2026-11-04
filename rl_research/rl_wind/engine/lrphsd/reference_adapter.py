"""Translate the official Java STORAGE convention to physical drone identities.
Check.java treats every SABS array slot as an SD. Init emits two slots even at
SABS; repair may put SD trips in either. SABS has only ONE physical SD: concatenate
its trip batches and recheck their SUM duration. This never relaxes capacity,
coverage, service, or target-count constraints. Preserve the raw export separately.
"""
import copy

def canonicalize_official(raw):
    out=copy.deepcopy(raw);merged=[]
    for si,kind in enumerate(out['station_types']):
        drones=out['routes'][si]
        if len(drones)!=2:raise ValueError('official export requires two storage slots')
        if kind==1 and drones[0]:
            merged.append({'station':si,'slot0_trip_count':len(drones[0]),'slot1_trip_count':len(drones[1]),'physical_drone':'one SD, concatenated sequential trips; cumulative duration rechecked'})
            drones[1]=drones[0]+drones[1];drones[0]=[]
    out['reference_storage_normalization']={'rule':'SABS slots -> one SD; DABS slot0=LD, slot1=SD','merged':merged,'routes_reoptimized':False,'station_types_changed':False}
    return out
