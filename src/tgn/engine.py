"""确定性、单行动结算引擎。"""
from __future__ import annotations
import copy, hashlib, json, secrets, uuid
from typing import Any
from .locales import normalize_locale, label
from .models import Campaign, Event
from .worldgen import generate_world

class DomainError(Exception): pass
class InvalidActionError(DomainError): pass

def _digest(seed,turn,action,counter=0):
 return int.from_bytes(hashlib.sha256(f"{seed}+{turn}+{action}+{counter}".encode()).digest()[:8],"big")
def _event_hash(prev,event_data):
 return hashlib.sha256(json.dumps({"prev_hash":prev,**event_data},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _append_event(c,kind,action,public,hidden=None):
 prev=c.events[-1].event_hash if c.events else "0"*64; data={"turn":c.turn,"kind":kind,"action_id":action,"public_facts":public,"hidden_facts":hidden or {}}
 c.events.append(Event(prev_hash=prev,event_hash=_event_hash(prev,data),**data))
def _state_summary(c):
 return {"schema_version":c.schema_version,"campaign_id":c.campaign_id,"seed":c.seed,"locale":c.locale,"premise":c.premise,"status":c.status,"finished":c.finished,"tier":c.tier,"turn":c.turn,"clock":c.clock,"world":c.world,"player":c.player,"factions":c.factions,"rival":c.rival,"opportunities":c.opportunities,"hidden":c.hidden,"knowledge":c.knowledge,"chapters":c.chapters,"events":[e.event_hash for e in c.events]}
def _set_digest(c):
 c.status_digest=hashlib.sha256(json.dumps(_state_summary(c),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def create_campaign(premise,locale="zh-CN",seed=None,campaign_id=None):
 if not isinstance(premise,str) or not premise.strip() or len(premise)>1000: raise ValueError("premise must be 1-1000 characters")
 loc=normalize_locale(locale); seed_value=str(seed) if seed is not None else secrets.token_hex(16)
 cid=campaign_id or f"c_{uuid.uuid4().hex[:12]}"; world=generate_world(premise,seed_value,loc)
 player={"name":"protagonist","resources":{"energy":5,"max_energy":5,"vitality":5,"max_vitality":5,"insight":3,"core":2,"influence":0,"risk_exposure":0},"abilities":{"observe":1,"gather":1,"convert":0,"negotiate":0,"organize":0,"rule_use":0},"assets":[],"relations":{},"control_score":0,"lifetime_control":0,"tier_control":0,"history":[]}
 c=Campaign("1.0",cid,seed_value,loc,premise,"active",1,0,0,world,player,copy.deepcopy(world["factions"]),copy.deepcopy(world["rival"]),copy.deepcopy(world["opportunities"]),{"contradiction":f"{world['common_risk']} feeds on {world['core_mechanism']}","discovered":False})
 _append_event(c,"genesis",None,{"message":label(loc,"start"),"title":world["title"],"control_axis":world["control_axis"],"region":world["initial_region"]})
 c.chapters.append({"turn":0,"text":world["title"]})
 _set_digest(c); return c,status_packet(c)

def status_packet(c):
 p=c.player
 rule_known="core_rule" in c.knowledge
 world={k:c.world[k] for k in ("title","control_axis","primary_resource","common_risk","initial_region","regions","anchors")}
 if rule_known:
  world["core_rule"]=c.world["core_rule"]
  world["leverage"]=copy.deepcopy(c.world["leverage"])
 else:
  world["core_rule"]=None
  world["leverage"]={"discovered":False,"condition":label(c.locale,"undiscovered")}
 return {"schema_version":c.schema_version,"campaign_id":c.campaign_id,"locale":c.locale,"status":c.status,"finished":c.finished,"tier":c.tier,"turn":c.turn,"clock":c.clock,"world":world,"player":{"resources":dict(p["resources"]),"abilities":dict(p["abilities"]),"assets":list(p["assets"]),"relations":dict(p["relations"]),"control_score":p["control_score"],"lifetime_control":p["lifetime_control"],"tier_control":p["tier_control"]},"factions":[{k:f[k] for k in ("id","name","stance","trust","pressure")} for f in c.factions],"rival":{k:c.rival[k] for k in ("id","name","progress","threat")},"opportunities":[dict(o) for o in c.opportunities],"knowledge":list(c.knowledge),"available_actions":available_actions(c),"latest_event":c.events[-1].public_facts if c.events else None}

def _can(p,cost): return all(p["resources"].get(k,0)>=v for k,v in cost.items())
def available_actions(c):
 if c.status!="active": return []
 p,r=c.player,c.player["resources"]; out=[]
 if r["vitality"]<=0:
  return [{"action_id":"recover","label":label(c.locale,"recover"),"cost":{},"reason":label(c.locale,"reason_basic")}] 
 def add(i,cost,reason):
  if _can(p,cost): out.append({"action_id":i,"label":label(c.locale,i),"cost":cost,"reason":label(c.locale,reason)})
 add("observe_rule",{"energy":1},"reason_always"); add("gather_resource",{"energy":1},"reason_basic")
 if "core_rule" in c.knowledge: add("convert_leverage",dict(c.world["leverage"]["action_cost"]),"reason_rule")
 if p["abilities"]["negotiate"]>0 or r["influence"]>=1: add("negotiate",{"energy":1},"reason_rule")
 if p["abilities"]["organize"]>0 or len(p["assets"])>=1 or r["influence"]>=1: add("organize",{"energy":1,"influence":1},"reason_rule")
 if p["abilities"]["rule_use"]>0 or p["abilities"]["convert"]>0: add("exploit_rule",{"energy":1},"reason_rule")
 if p["tier_control"]>=8: add("ascend",{"energy":2,"influence":2},"reason_threshold")
 if r["energy"]<r["max_energy"] or r["vitality"]<r["max_vitality"]: out.append({"action_id":"recover","label":label(c.locale,"recover"),"cost":{},"reason":label(c.locale,"reason_basic")})
 return out

def _tick(c,digest):
 before={"rival":c.rival["progress"],"threat":c.rival["threat"],"factions":[f["pressure"] for f in c.factions],"opportunities":[(o["id"],o["remaining"]) for o in c.opportunities]}; c.clock+=1
 for i,f in enumerate(c.factions): f["pressure"]=max(0,f["pressure"]+(1 if (digest+i)%3==0 else -1 if (digest+i)%5==0 else 0)); f["trust"]=max(-5,min(5,f["trust"]+(1 if c.player["control_score"]>5 and i==0 else 0)))
 c.rival["progress"]+=1+digest%2; c.rival["threat"]=min(10,c.rival["threat"]+(1 if c.rival["progress"]%4==0 else 0))
 for o in c.opportunities: o["remaining"]-=1
 c.opportunities[:]=[o for o in c.opportunities if o["remaining"]>0]
 return {"factions":[{"id":f["id"],"pressure":f["pressure"],"trust":f["trust"]} for f in c.factions],"rival":{"progress":c.rival["progress"],"threat":c.rival["threat"]},"opportunities":[dict(o) for o in c.opportunities],"before":before}

def settle_action(campaign,action_id):
 legal={a["action_id"]:a for a in available_actions(campaign)}
 if action_id not in legal: raise InvalidActionError(f"{label(campaign.locale,'reason_unavailable')}: {action_id!r}")
 c=campaign.clone(); p,r=c.player,c.player["resources"]; c.turn+=1; value=_digest(c.seed,c.turn,action_id,len(c.events)); roll=value%100; hidden={}; public={"action_id":action_id,"turn":c.turn,"roll":roll,"threshold":0,"success":True}
 if action_id=="recover":
  de=r["max_energy"]-r["energy"]; dv=min(r["max_vitality"],r["vitality"]+2)-r["vitality"]; r["energy"]=r["max_energy"]; r["vitality"]+=dv; public.update({"cost":{},"gained":{"energy":de,"vitality":dv}})
 elif action_id=="observe_rule":
  r["energy"]-=1; r["insight"]+=1; p["abilities"]["observe"]+=1
  if "core_rule" not in c.knowledge: c.knowledge.append("core_rule")
  c.hidden["discovered"]=True; public.update({"cost":{"energy":1},"gained":{"insight":1},"knowledge":"core_rule","discovered_contradiction":c.world["core_rule"]})
 else:
  cost=legal[action_id]["cost"]
  for k,v in cost.items(): r[k]-=v
  public["cost"]=dict(cost)
  threshold=45; bonus=sum(o["bonus"] for o in c.opportunities if o["bonus_action"]==action_id); threshold=max(15,threshold-bonus-p["abilities"].get("observe",0)*3-(5 if "core_rule" in c.knowledge else 0)); public["threshold"]=threshold; public["opportunity_bonus"]=bonus
  if action_id=="convert_leverage":
   success=roll>=threshold
   if success:
    gain=1+c.world["leverage"]["mastery"]+bonus; r["risk_exposure"]+=1; r["influence"]+=gain; p["abilities"]["convert"]+=1; p["control_score"]+=gain; p["lifetime_control"]+=gain; p["tier_control"]+=gain; c.world["leverage"]["mastery"]+=1; p["assets"].append(f"lever_{c.turn}"); axis=c.world["control_axis"]; extra={}
    if axis=="resource_production": r["core"]+=gain; p["abilities"]["gather"]+=1; extra={"core":gain}
    elif axis=="knowledge_memory": r["insight"]+=1; extra={"insight":1}
    elif axis=="law_identity": p["abilities"]["rule_use"]+=1; extra={"rule_use":1}
    elif axis=="space_environment": r["max_energy"]+=1; extra={"max_energy":1}
    elif axis=="relationship_trust":
     target=c.factions[(value//7)%len(c.factions)]; target["trust"]=min(5,target["trust"]+1); p["relations"][target["id"]]=target["trust"]; extra={"trust":1,"faction":target["id"]}
    else:
     p["abilities"]["rule_use"]+=1; p["assets"].append(f"resonance_{c.turn}"); extra={"resonance":gain,"rule_use":1}
    public.update({"gained":{"influence":gain,**extra},"formula_input":{"core":1,"insight":1,"mastery":c.world["leverage"]["mastery"]-1},"formula_output":gain,"cost":dict(cost,risk_exposure=1)})
   else:
    r["risk_exposure"]+=1; r["vitality"]-=1; public.update({"loss":{"vitality":1},"reason":label(c.locale,"failure_reason"),"formula_input":{"core":1,"insight":1},"cost":dict(cost,risk_exposure=1)})
  else: success=roll>=threshold
  if action_id!="convert_leverage":
   if success:
    if action_id=="gather_resource": gain=2+bonus+p["abilities"].get("gather",0)-1; r["core"]+=gain; p["control_score"]+=1; p["lifetime_control"]+=1; p["tier_control"]+=1; public["gained"]={"core":gain}
    elif action_id=="negotiate": p["abilities"]["negotiate"]+=1; r["influence"]+=1; p["control_score"]+=1; p["lifetime_control"]+=1; p["tier_control"]+=1; target=c.factions[value%3]; target["trust"]=min(5,target["trust"]+1); public["faction"]=target["id"]; public["gained"]={"influence":1}
    elif action_id=="organize": p["abilities"]["organize"]+=1; p["assets"].append(f"cell_{c.turn}"); p["control_score"]+=2; p["lifetime_control"]+=2; p["tier_control"]+=2; public["gained"]={"organization":1}
    elif action_id=="exploit_rule": p["abilities"]["rule_use"]+=1; r["core"]+=3; p["control_score"]+=2; p["lifetime_control"]+=2; p["tier_control"]+=2; public["gained"]={"core":3}
   else:
    loss={"vitality":1,"risk_exposure":1}; r["vitality"]-=1; r["risk_exposure"]+=1
    if action_id=="negotiate": loss["influence"]=1; r["influence"]=max(0,r["influence"]-1)
    if action_id=="gather_resource": loss["core"]=1; r["core"]=max(0,r["core"]-1)
    public["loss"]=loss; public["reason"]=label(c.locale,"failure_reason"); success=False
  public["success"]=success
  if action_id=="ascend" and success:
   c.tier+=1; p["tier_control"]=0; loc=c.locale; names={"zh-CN":f"第{c.tier}层中枢","fr-FR":f"Méridien du palier {c.tier}","en":f"Tier {c.tier} Meridian","ar":f"خط الزوال للمستوى {c.tier}"}; fac={"zh-CN":f"第{c.tier}层守门者","fr-FR":f"Gardiens du palier {c.tier}","en":f"Tier {c.tier} Custodians","ar":f"حراس المستوى {c.tier}"}; c.world["regions"].append({"id":f"region_{c.tier}","name":names[loc],"tier":c.tier}); c.world["factions"].append({"id":f"faction_tier_{c.tier}","name":fac[loc],"stance":label(loc,"reason_rule"),"trust":0,"pressure":c.tier,"agenda":c.world["core_mechanism"]}); c.factions.append(copy.deepcopy(c.world["factions"][-1])); c.world["opportunities"].append({"id":f"window_tier_{c.tier}","name":names[loc],"remaining":6,"bonus_action":"exploit_rule","bonus":2}); c.opportunities.append(copy.deepcopy(c.world["opportunities"][-1])); c.world["tier_layers"].append({"tier":c.tier,"rule_pressure":c.tier*2}); public.update({"tier":c.tier,"retained":{"assets":len(p["assets"]),"abilities":dict(p["abilities"]),"lifetime_control":p["lifetime_control"]}})
 response=_tick(c,value); public["world_response"]=response; p["history"].append({"turn":c.turn,"action_id":action_id,"result":copy.deepcopy(public)}); c.chapters.append({"turn":c.turn,"text":label(c.locale,action_id)}); _append_event(c,"action",action_id,public,hidden); _set_digest(c); return c,status_packet(c)

def finish_campaign(campaign):
 if campaign.status=="finished": return campaign.clone(),status_packet(campaign)
 c=campaign.clone(); c.turn+=1; c.status="finished"; c.finished=True; pub={"finished":True,"turn":c.turn,"tier":c.tier,"control_score":c.player["control_score"]}; _append_event(c,"finish",None,pub,{}); c.chapters.append({"turn":c.turn,"text":label(c.locale,"finished")}); _set_digest(c); return c,status_packet(c)
