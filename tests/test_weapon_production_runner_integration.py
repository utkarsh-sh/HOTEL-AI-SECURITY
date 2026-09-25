import numpy as np
import ai.run_intrusion_detection as runner
from ai.weapon_event_processor import WeaponEventProcessor
from database.event_database import EventDatabase

class Source:
    def __init__(self, frame): self.frame, self.n = frame, 0
    def read(self):
        self.n += 1
        return self.frame if self.n <= 3 else None
class Manager:
    def __init__(self,s): self.s=s
    def get_source(self,camera_id): return self.s
class CamDB:
    def get_camera(self,camera_id): return {'camera_id':camera_id,'name':'Test','location':'Test','status':'ONLINE','consecutive_failures':0}
class Health:
    def __init__(self,*a,**k): pass
    def frame_received(self,*a,**k): return None
    def frame_failed(self,*a,**k): return None
    def get_failure_count(self): return 0
    def is_offline(self): return False
class Writer:
    def __init__(self): self.frames=0; self.released=False
    def isOpened(self): return True
    def write(self,frame): self.frames += 1
    def release(self): self.released=True
class Evidence:
    def __init__(self,*a,**k): pass
    def add_frame(self,frame): pass
    def start_event_capture(self,*a,**k): pass
    def finalize(self): pass
class Person:
    def detect(self,frame): return [{'class':'person','confidence':0.99,'box':[50,50,300,350]}]
class Tracker:
    def update(self,d): return [{'track_id':7,'box':[50,50,300,350],'state':'TRACKED'}]
class Zone:
    def check_tracks(self,t): return []
class Intrusion:
    def __init__(self,*a,**k): pass
    def evaluate(self,z): return []
class Fall:
    def __init__(self,*a,**k): pass
    def evaluate(self,t): return []
class Provider:
    def __call__(self,frame): return [{'class_name':'gun','confidence':0.95,'box':[110,120,150,170]}]
class Dispatcher:
    def __init__(self): self.calls=[]
    def notify_event(self,**kw): self.calls.append(kw); return 'future'

def cfg(): return type('Cfg',(),{'camera_id':'CAM-001','name':'Test','location':'Test','source_type':'FILE','ai_fps':1.0})()

def test_weapon_runner_pipeline(monkeypatch,tmp_path):
    frame=np.zeros((480,640,3),dtype=np.uint8)
    writer=Writer(); dispatcher=Dispatcher(); db=EventDatabase(tmp_path/'events.db')
    monkeypatch.setattr(runner,'get_capture_metadata',lambda s:(1.0,3,640,480))
    monkeypatch.setattr(runner,'is_finite_source',lambda c:True)
    monkeypatch.setattr(runner.cv2,'VideoWriter',lambda *a,**k:writer)
    monkeypatch.setattr(runner,'EvidenceRecorder',Evidence)
    monkeypatch.setattr(runner,'CameraHealthMonitor',Health)
    monkeypatch.setattr(runner,'PersonTracker',Tracker)
    monkeypatch.setattr(runner,'IntrusionRule',Intrusion)
    monkeypatch.setattr(runner,'FallEventProcessor',Fall)
    result=runner.process_camera(cfg(),Manager(Source(frame)),Person(),[],Zone(),db,CamDB(),object(),dispatcher,weapon_detection_provider=Provider(),weapon_event_processor=WeaponEventProcessor(persistence_frames=3))
    assert result['error'] is None
    assert result['events'] == 1
    events=db.get_all_events(); assert len(events)==1
    assert events[0]['event_type']=='WEAPON'; assert events[0]['track_id']==7
    assert events[0]['model_version']=='weapon-yolo11n-gun-knife-v1'
    assert dispatcher.calls[0]['subject']=='Hotel Security Alert - WEAPON'
    assert writer.released
    db.close()
