"""原创、可复现的多语言世界生成。"""
from __future__ import annotations
import hashlib, re
from .locales import normalize_locale

AXIS_DATA = {
 "resource_production": {"resource":"grain", "mechanism":"production cycles", "risk":"scarcity shocks", "formula":"core × cycle -> stock", "cost":{"energy":1,"risk_exposure":1}},
 "knowledge_memory": {"resource":"memory", "mechanism":"remembered patterns", "risk":"forgetting storms", "formula":"memory + insight -> durable map", "cost":{"insight":1,"risk_exposure":1}},
 "relationship_trust": {"resource":"trust", "mechanism":"reciprocal promises", "risk":"betrayal cascades", "formula":"trust + proof -> influence", "cost":{"energy":1,"risk_exposure":1}},
 "law_identity": {"resource":"legitimacy", "mechanism":"recognized names", "risk":"jurisdiction gaps", "formula":"name + witness -> mandate", "cost":{"influence":1,"risk_exposure":1}},
 "space_environment": {"resource":"safe ground", "mechanism":"route geometry", "risk":"shifting terrain", "formula":"route + timing -> access", "cost":{"energy":1,"risk_exposure":1}},
 "causal_resonance": {"resource":"resonance", "mechanism":"linked causes", "risk":"feedback loops", "formula":"cause + insight -> capability", "cost":{"insight":1,"risk_exposure":1}},
}
KEYWORDS = {
 "resource_production":("粮食","资源","生产","农场","grain","resource","production","récolte","ressource","إنتاج","مورد"),
 "knowledge_memory":("记忆","知识","档案","memory","knowledge","archive","mémoire","connaissance","ذاكرة","معرفة"),
 "relationship_trust":("信任","关系","盟约","trust","relationship","alliance","confiance","relation","ثقة","علاقة"),
 "law_identity":("法律","身份","契约","law","identity","contract","loi","identité","قانون","هوية"),
 "space_environment":("空间","路线","地形","space","route","terrain","espace","terrain","مسار","بيئة"),
 "causal_resonance":("因果","共振","循环","causal","resonance","feedback","causalité","résonance","سبب","رنين"),
}
T = {
 "zh-CN": {"title":"回声疆域", "factions":["砾光公社","衡线工坊","远岬使团"], "rival":"逆潮者弥安", "region":"初鸣台", "opp":["潮汐窗口","边界集市"], "anchors":["沉降塔","回声井","北门锚点"]},
 "fr-FR": {"title":"Territoire des échos", "factions":["Commune de Lueur","Atelier de la Ligne","Mission du Cap"], "rival":"Mian, le Contre-courant", "region":"Plateforme de l'Aube", "opp":["Fenêtre des marées","Marché frontière"], "anchors":["Tour d'affaissement","Puits d'écho","Ancre du Nord"]},
 "en": {"title":"Echo Territory", "factions":["Gravelight Commune","Linewright Atelier","Far-Cape Mission"], "rival":"Mian of the Countertide", "region":"First Resonance Deck", "opp":["Tide Window","Border Market"], "anchors":["Sinking Tower","Echo Well","North Anchor"]},
 "ar": {"title":"إقليم الصدى", "factions":["جماعة ضوء الحصى","ورشة الخط المتزن","بعثة الرأس البعيد"], "rival":"ميان عكس التيار", "region":"منصة الرنين الأول", "opp":["نافذة المد","سوق الحدود"], "anchors":["برج الهبوط","بئر الصدى","مرساة الشمال"]},
}
VARIANT_PREFIX = {
 "zh-CN": ["晨雾","赤岩","深蓝"],
 "fr-FR": ["Aube","Roche Rouge","Bleu Profond"],
 "en": ["Dawn","Redrock","Deepblue"],
 "ar": ["الفجر","الصخر الأحمر","الأزرق العميق"],
}
AXIS_TEXT = {
 "zh-CN": {"resource_production":("资源","生产循环","稀缺冲击"),"knowledge_memory":("记忆","记忆模式","遗忘风暴"),"relationship_trust":("信任","互惠承诺","背叛级联"),"law_identity":("正当性","承认的姓名","管辖空隙"),"space_environment":("安全地面","路线几何","地形漂移"),"causal_resonance":("共振","因果链","反馈回路")},
 "fr-FR": {"resource_production":("ressource","cycles de production","chocs de pénurie"),"knowledge_memory":("mémoire","motifs mémorisés","tempêtes d'oubli"),"relationship_trust":("confiance","promesses réciproques","cascades de trahison"),"law_identity":("légitimité","noms reconnus","failles de juridiction"),"space_environment":("sol sûr","géométrie des routes","terrain mouvant"),"causal_resonance":("résonance","causes liées","boucles de rétroaction")},
 "en": {"resource_production":("resource","production cycles","scarcity shocks"),"knowledge_memory":("memory","remembered patterns","forgetting storms"),"relationship_trust":("trust","reciprocal promises","betrayal cascades"),"law_identity":("legitimacy","recognized names","jurisdiction gaps"),"space_environment":("safe ground","route geometry","shifting terrain"),"causal_resonance":("resonance","linked causes","feedback loops")},
 "ar": {"resource_production":("المورد","دورات الإنتاج","صدمات الندرة"),"knowledge_memory":("الذاكرة","الأنماط المحفوظة","عواصف النسيان"),"relationship_trust":("الثقة","وعود متبادلة","سلاسل الخيانة"),"law_identity":("الشرعية","أسماء معترف بها","فجوات الاختصاص"),"space_environment":("الأرض الآمنة","هندسة المسارات","تضاريس متحركة"),"causal_resonance":("الرنين","أسباب مترابطة","حلقات ارتداد")},
}

def _num(seed,*parts):
 return int.from_bytes(hashlib.sha256(("|".join([str(seed),*map(str,parts)])).encode()).digest()[:8],"big")
def _slug(premise):
 w=re.findall(r"[\w\u4e00-\u9fff]+",premise,re.UNICODE); return "".join(w[:2])[:18] or "Frontier"
def _axis(premise,seed):
 low=premise.lower()
 for axis, words in KEYWORDS.items():
  if any(w.lower() in low for w in words): return axis
 return tuple(AXIS_DATA)[_num(seed,premise,"axis")%len(AXIS_DATA)]

def generate_world(premise: str, seed: str, locale: str = "zh-CN") -> dict:
 loc=normalize_locale(locale); axis=_axis(premise,seed); d=AXIS_DATA[axis]; t=T[loc]; tx=AXIS_TEXT[loc][axis]
 factions=[]; variant=(int(str(seed))%3 if str(seed).isdigit() else _num(seed,premise,"names")%3)
 stances=("谨慎","逐利","守序") if loc=="zh-CN" else (("prudent","profit-seeking","lawful") if loc=="en" else (("prudent","avide","ordonné") if loc=="fr-FR" else ("حذر","ربحي","منظم")))
 prefix=VARIANT_PREFIX[loc][variant]
 for i,name in enumerate(t["factions"]):
  factions.append({"id":f"faction_{i+1}","name":f"{prefix} {name}","stance":stances[i],"trust":0,"pressure":1+_num(seed,axis,i)%3,"agenda":tx[1]})
 opp=[]
 for i,name in enumerate(t["opp"]):
  opp.append({"id":f"window_{i+1}","name":name,"remaining":5+i*3,"bonus_action":"convert_leverage" if i==0 else "negotiate","bonus":2-i})
 return {"title":f"{_slug(premise)} · {t['title']}","premise":premise,"control_axis":axis,
  "primary_resource":tx[0],"core_mechanism":tx[1],"common_risk":tx[2],
  "core_rule":(f"{tx[0]}沿{tx[1]}放大，也会因{tx[2]}反噬" if loc=="zh-CN" else f"{tx[0]} follows {tx[1]} and rebounds through {tx[2]}" if loc=="en" else f"La {tx[0]} suit les {tx[1]} et revient par les {tx[2]}" if loc=="fr-FR" else f"يتبع {tx[0]} {tx[1]} ويرتد عبر {tx[2]}"),
  "leverage":{"id":f"{axis}_lever","name":tx[0],"formula":(f"{tx[0]} + 洞察 -> 能力" if loc=="zh-CN" else f"{tx[0]} + insight -> capability" if loc=="en" else f"{tx[0]} + intuition -> capacité" if loc=="fr-FR" else f"{tx[0]} + بصيرة -> قدرة"),"condition":("掌握核心规则" if loc=="zh-CN" else "core rule known" if loc=="en" else "règle centrale connue" if loc=="fr-FR" else "معرفة القاعدة الأساسية"),"action_cost":{"energy":1,"insight":1,"core":1},"effect":(f"精通提高{tx[1]}效率" if loc=="zh-CN" else f"mastery improves {tx[1]}" if loc=="en" else f"la maîtrise améliore {tx[1]}" if loc=="fr-FR" else f"الإتقان يحسن {tx[1]}"),"efficiency":1,"cost":{"risk_exposure":1},"mastery":0},
  "initial_region":{"id":"region_0","name":f"{prefix} {t['region']}","safety":3},"regions":[{"id":"region_0","name":f"{prefix} {t['region']}","tier":1}],"anchors":[f"{prefix} {a}" for a in t["anchors"]],
  "factions":factions,"rival":{"id":"rival_1","name":f"{prefix} {t['rival']}","progress":0,"strategy":tx[1],"threat":2},"opportunities":opp,"tier_layers":[]}
