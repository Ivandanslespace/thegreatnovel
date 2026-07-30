# 《صدع الهاوية》对话记录

---

<!-- narrative-turn:1 -->
## 第1回 · Day 1 清晨

### 玩家原始输入

بدأتُ لعبة جديدة باللغة العربية.

### GM完整回答

استيقظتَ على اهتزاز معدني عميق، كأن شيئاً هائلاً يمر تحت الأرض. المأوى المتنقل يدور ببطء حول حافة صدع أسود لا يظهر له قاع. خلف الجدران، تهب رياح باردة محمّلة بذرات رمادية، وفي البعيد يلمع ضوء خاطف داخل الضباب.

أنت آمن مؤقتاً داخل المأوى، لكن الطعام ومواد الأدوات والطاقة الأساسية غير متوفرة. لديك موهبة «نذير الخطر»: تستطيع الإحساس بالتغيرات غير المألوفة عند دخول منطقة مجهولة، لكنها لا تغني عن الاستطلاع.

【لوحة النظام】
المستوى: 1　الخبرة: 0/100
القوة: 5　التحمل: 5　الرشاقة: 5　الروح: 5
الحياة: 50/50　الحالة: طبيعي
القاعدة: المأوى المتنقل　المستوى 1
الزمن: اليوم الأول — الفجر

الصدع ينتظر خلف الباب. ما خطوتك الأولى؟

A. استطلاع حافة الصدع
اخرج بحذر للبحث عن موارد أو علامات خطر، مع الحفاظ على مسار عودة واضح.
→ المتوقع: معلومات وموارد محتملة / تعرّض للخطر واستهلاك الوقت

B. فحص المأوى
افحص هيكل المأوى ومحيطه القريب بحثاً عن أدوات أو عيوب أو آثار سكان سابقين.
→ المتوقع: معرفة آمنة بالقاعدة / موارد أقل وفرصة ضائعة للاستطلاع البعيد

C. مراقبة الصدع من الداخل
راقب الضوء والضباب وحركة الرياح لتحديد نمط الخطر قبل فتح الباب.
→ المتوقع: معلومات أولية مع خطر منخفض / تأخر في جمع الموارد

D. فعل حر
صف ما تريد فعله، وسأحوّله إلى إجراء قابل للتحقق وفق قواعد العالم.

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0001_001",
  "type": "WORLD_CREATED",
  "actor": "system",
  "target": null,
  "data": {
    "world_name": "صدع الهاوية",
    "theme": "صدع الهاوية",
    "safe_base": "围绕主题建立的移动避难所",
    "difficulty": "标准"
  },
  "turn": 1,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:2 -->
## 第2回 · Day 1 清晨

### 玩家原始输入

Ok

### GM完整回答

نتيجة المعاينة من المحرك:

- الإجراء قانوني.
- سيستغرق جزءاً كبيراً من وقت الفجر.
- سيستهلك قدراً من الطاقة الجسدية والذهنية.
- النتيجة المتوقعة: فشل جزئي مع الحصول على بعض المعلومات.
- لا توجد وفاة في هذه المعاينة.
- لم يتغير الحفظ بعد.

تم تأكيد التنفيذ.

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0002_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "الصدع من الداخل",
  "data": {
    "action": {
      "action_id": "observe-rift-001",
      "type": "EXPLORATION",
      "target": "الصدع من الداخل",
      "primary_attribute": "spirit"
    },
    "action_ledger": {
      "available_time_minutes": 240.0,
      "available_stamina": 100.0,
      "available_mental": 100.0,
      "actions": [
        {
          "type": "EXPLORATION",
          "target": "الصدع من الداخل",
          "time_minutes": 120.0,
          "stamina_cost": 15.0,
          "mental_cost": 10.0,
          "tags": [
            "observation"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "observe-rift-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 25.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 0.0,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 28.0,
      "K": 10.0,
      "probability": 0.214165,
      "random_roll": 0.092241,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "失败但获得部分信息",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 5.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 15.0,
    "mental_delta": -10.0,
    "time_cost": 120.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 2,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:3 -->
## 第3回 · Day 1 清晨

### 玩家原始输入

Ok

### GM完整回答

نتيجة المعاينة من المحرك:

- الإجراء قانوني.
- الوقت المتاح يكفي تماماً لهذه المراقبة.
- الحالة الحالية تزيد صعوبة التركيز.
- النتيجة المتوقعة: فشل شديد.
- لا توجد وفاة، لكن قد تحدث عاقبة سلبية مهمة.
- لم يتغير الحفظ بعد.

تم تأكيد التنفيذ.

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0003_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "الصدع من الداخل",
  "data": {
    "action": {
      "action_id": "observe-rift-002",
      "type": "EXPLORATION",
      "target": "الصدع من الداخل",
      "primary_attribute": "spirit"
    },
    "action_ledger": {
      "available_time_minutes": 120.0,
      "available_stamina": 85.0,
      "available_mental": 90.0,
      "actions": [
        {
          "type": "EXPLORATION",
          "target": "الصدع من الداخل",
          "time_minutes": 120.0,
          "stamina_cost": 15.0,
          "mental_cost": 10.0,
          "tags": [
            "observation"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "observe-rift-002",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 25.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 3.0,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 31.0,
      "K": 10.0,
      "probability": 0.167982,
      "random_roll": 0.956331,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "严重失败",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 5.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 15.0,
    "mental_delta": -10.0,
    "time_cost": 120.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 3,
  "timestamp": "Day 1 清晨"
}
```
