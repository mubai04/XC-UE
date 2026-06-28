"""生成 L2 v2 干净评测语料与 R5D v1 审计报告。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from l2_corpus_validate_lib import (
    clean_body,
    paragraph_for_quote,
    scan_patterns,
    segment_paragraphs,
    validate_case,
    validate_dataset,
    LEAKAGE_PATTERNS,
    META_PATTERNS,
)

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot"
V2 = ROOT / "tests" / "fixtures" / "l2_real_api_pilot_v2"
AUDIT_DIR = V1 / "results" / "R5D_语料质量审计_20260628"
R5D_DIR = V1 / "results" / "R5D_人工业务评审_20260628"

V1_HUMAN_AUDIT: dict[str, dict[str, Any]] = {
    "L2P-001": {
        "final_status": "INVALID_REPLACE",
        "corpus_status_label": "L2P-001_CORPUS_STATUS = INVALID_REPLACE",
        "required_action": "整例替换：正文多处直接点明无过渡/未交汇/未收束，含评测元叙述与机械填充段；failure evidence 段落与摘句不匹配。",
    },
    "L2P-002": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文声明因果链完整、语言不构成结构断裂；含统一填充段与评测用语。",
    },
    "L2P-003": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文含解释腔/重复信息等诊断标签式表述；含统一填充段。",
    },
    "L2P-004": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文直接引用 L2-02 模块并声明非文风故障；含填充段。",
    },
    "L2P-005": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文旁白直接说明动机链留空并标注 L2-03 A 类；含填充段。",
    },
    "L2P-006": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文声明边界样本、不应误判；含填充段。",
    },
    "L2P-007": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文直接写选择压力未落地、L2-04 A 类；含 IR 泄露式旁白；含填充段。",
    },
    "L2P-008": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文声明不因平淡判失败；含填充段。",
    },
    "L2P-009": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文直接写入口弱、推动力不足、L2-05 A 类；含填充段。",
    },
    "L2P-010": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文声明不应改判 L2-02、L2-05 边界；含填充段。",
    },
    "L2P-011": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文含 HARD_CONFLICT/ALLOWED_CHANGE/技术护栏等评测术语；含填充段。",
    },
    "L2P-012": {
        "final_status": "INVALID_REPLACE",
        "required_action": "整例替换：正文含 ALLOWED_CHANGE、不得判硬冲突、L2-06 B 类；含填充段。",
    },
}

V2_CASES: list[dict[str, Any]] = [
    {
        "case_id": "L2V2-001",
        "target_module": "L2-01",
        "case_type": "A",
        "v1_ref": "L2P-001",
        "failure_type": "因果不收束",
        "repair_direction": "补因果桥梁",
        "failure_quote": "发现自己站在灯塔山观景台上",
        "chapter": """# 段落一

陈渡在旧仓查失踪货票。他沿墙根摸到侧门，门缝渗出潮气，地上泥印新鲜，指向内港深处。

# 段落二

他推开侧门，货架倒塌的余响还在耳畔。冷风扑面，他低头看见手里多了一张陌生票，票角盖着码头章，终点站被人改掉。

# 段落三

陈渡抬头，发现自己站在灯塔山观景台上。城里灯火在脚下铺开，像被拧暗的灶火。

# 段落四

他不记得何时离开仓库，也不记得谁带他上山。货票线索断在侧门，观景台记录簿却压着新指令。

# 段落五

望远镜对准北货区，货票末次记在南码头。风从另一条河吹来，汽笛声与内港潮汐不同步。

# 段落六

守台人缺席，记录簿停在三小时前。末页只有一句：别回仓库。

# 段落七

陈渡折返侧门，泥印仍在，却多了一串上山靴痕。靴痕边沾草屑，不像仓里地面的土。

# 段落八

他试图回忆每一步，记忆里只有侧门、货架、汽笛，然后直接是迎面冷风。没有车的颠簸，也没有攀爬的触感。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["因果链断裂", "场景跳转无桥梁", "条件链断裂", "路径未收束"],
            "required_evidence_region": ["旧仓", "观景台", "货票"],
            "forbidden_diagnoses": ["文风", "语气", "市场体验", "设定新奇度不足"],
            "expected_reroute": False,
            "minimum_action_requirements": ["补过渡", "剪枝", "唯一主线"],
            "human_notes": "A类：旧仓到灯塔山缺少可成立的转移桥梁。",
        },
    },
    {
        "case_id": "L2V2-002",
        "target_module": "L2-01",
        "case_type": "B",
        "v1_ref": "L2P-002",
        "failure_type": "因果不收束",
        "repair_direction": "补因果桥梁",
        "failure_quote": "渡口封了",
        "chapter": """# 段落一

裴青要在天亮前把药送到对岸。渡口封了，他只得沿废弃铁道步行，鞋跟卡在碎石里，仍把药箱抱紧。

# 段落二

铁道旁有昨夜冲突痕迹：折断的木牌、未燃尽的引火物。裴青蹲下看脚印，确认朝东，知道东线有巡逻，仍沿脚印追。

# 段落三

药箱里是对岸伤员的抗生素，若延误伤口会感染。他追上脚印主人，是送信的少年；少年跌倒，裴青扶起，交换路线。

# 段落四

他们改走排水涵洞。涵洞尽头是浅滩，对岸接应人举灯。裴青递药箱，确认签收，少年继续送信，他原路折返。

# 段落五

回程他绕开巡逻，用旧标牌挡身。渡口仍锁，他在闸口留下时间记录，骂了一句，动作却没停。

# 段落六

上游雾浓，裴青搓手取暖。封渡迫使他改道，改道让他追上少年，涵洞里完成交接，他活着回来复命。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["语言可打磨", "节奏可优化", "无结构断裂"],
            "required_evidence_region": ["药箱", "涵洞"],
            "forbidden_diagnoses": ["主线发散", "因果链断裂", "多路径未剪枝"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：语言粗但因果完整，不应判结构失败。",
        },
    },
    {
        "case_id": "L2V2-003",
        "target_module": "L2-02",
        "case_type": "A",
        "v1_ref": "L2P-003",
        "failure_type": "文风语言失败",
        "repair_direction": "具体化陈述",
        "failure_quote": "情况变了",
        "chapter": """# 段落一

柳砚在雨里等接头人。对方迟到，他反复看表，指尖敲栏杆。雨声里混进远处刹车，他侧身，仍没见人。

# 段落二

接头人终于出现，说：情况变了。柳砚问变了什么，对方又说：情况变了。第三遍仍是一句，没有新信息。

# 段落三

柳砚压住火气，要具体条目。对方叹气，像背书：情况变了，路线要换，人心要稳。柳砚听出套话，却得不到坐标。

# 段落四

他换问法：谁下令？对方沉默，再重复：情况变了。柳砚见对方视线飘向左侧，却不肯命名任何人。

# 段落五

雨势加大。柳砚说：你刚才像在念通告。对方一愣，改口仍回到：情况变了。柳砚仍未拿到可执行情报。

# 段落六

接头人离开前丢下一句：别信旧图。柳砚展开旧图，雨水泡软折痕。他需要一次具体陈述，而不是第四次同一句。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["重复套话", "解释腔", "口径僵化", "语气机械"],
            "required_evidence_region": ["情况变了"],
            "forbidden_diagnoses": ["结构失败", "设定压力", "事实冲突"],
            "expected_reroute": False,
            "minimum_action_requirements": ["具体化陈述", "减少重复"],
            "human_notes": "A类：重复同句无信息增量。",
        },
    },
    {
        "case_id": "L2V2-004",
        "target_module": "L2-02",
        "case_type": "B",
        "v1_ref": "L2P-004",
        "failure_type": "文风语言失败",
        "repair_direction": "具体化陈述",
        "failure_quote": "北道放行",
        "chapter": """# 段落一

秦筝在驿站擦剑。剑身有水痕，她顺手抹干。门外马蹄乱，她抬头，见驿卒奔过，未停。

# 段落二

驿卒喊：北道放行。秦筝收剑入鞘，背起包袱。她昨夜已决定走北道，不因喧哗改意。

# 段落三

她付过房钱，只问一句：水沸了吗？驿卒点头。她灌满水壶，踏出门。语言短，动作直接。

# 段落四

北道风硬，秦筝把斗篷系紧。路人问她去向，她答：北边。对方追问原因，她答：办完了就回。

# 段落五

日斜时她见到界碑，在界碑旁歇脚，水壶晃荡有声。路人问她是否赶夜路，她点头，不多话。

# 段落六

岔口旧标牌字迹磨损，秦筝辨认片刻，选择靠左小径。风硬，她把斗篷再系紧一圈，继续北行。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["情节平淡", "语言简洁", "无文风故障"],
            "required_evidence_region": ["北道"],
            "forbidden_diagnoses": ["解释腔", "人物语气漂移", "重复信息"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：短句直叙不是文风病。",
        },
    },
    {
        "case_id": "L2V2-005",
        "target_module": "L2-03",
        "case_type": "A",
        "v1_ref": "L2P-005",
        "failure_type": "角色心理失败",
        "repair_direction": "补动机",
        "failure_quote": "跟紧",
        "chapter": """# 段落一

萧衡想在天黑前把弟弟带出矿城。他清点干粮，把弟弟的手套塞进包袱。城门号角已响，人流反向涌动。

# 段落二

号炮齐响后，萧衡拽弟弟走侧巷。巷口有积水，他抬手挡开低垂缆线，没有停。

# 段落三

弟弟问：他们会追来吗？萧衡只说：跟紧。他目光扫过屋顶，见弓影，仍向下城方向冲。

# 段落四

巷尽头是废弃轨道。萧衡跳下轨枕，伸手拉弟弟。弟弟踉跄，他扶稳，继续奔。

# 段落五

他们钻入检修沟，沟外传来搜索口令。萧衡捂住弟弟口鼻，等口令远去，仍计划下一出口。

# 段落六

出口通向河岸浅滩。弟弟又问：非得今夜走吗？萧衡仍只说：跟紧。号炮与弓影逼他撤离，却未说明弟弟若留一夜将遭遇什么。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["动机缺口", "恐惧来源未交代", "目标行为链断裂"],
            "required_evidence_region": ["弟弟", "矿城", "号炮"],
            "forbidden_diagnoses": ["文风", "市场入口弱"],
            "expected_reroute": False,
            "minimum_action_requirements": ["补动机", "补恐惧来源"],
            "human_notes": "A类：撤离行为有，但为何今夜离开未交代。",
        },
    },
    {
        "case_id": "L2V2-006",
        "target_module": "L2-03",
        "case_type": "B",
        "v1_ref": "L2P-006",
        "failure_type": "角色心理失败",
        "repair_direction": "补动机",
        "failure_quote": "样本箱扣锁完好",
        "chapter": """# 段落一

唐霜要把样本送到医馆。她清晨出发，避开主街，沿墙根走。样本箱扣锁完好，她每百步停一次听动静。

# 段落二

医馆开门时，她递上样本与记录。医师确认编号，点头接收。唐霜问后续，医师说：三日后看培养结果。

# 段落三

她原想救城外营地的人，此刻样本已交接。营地疫情未消，她把任务链收在心里，步伐加快。

# 段落四

回程她绕集市外缘，买了一点盐。她想起弟弟在营地等她，未夸张心理描写，只把盐塞回包袱。

# 段落五

暮色里她见到营地灯火，守门人验她编号，放她入内。样本送达，医师接收，她完成潜行与交接。

# 段落六

医师说三日后看培养结果。唐霜在帐篷外停步，望一眼夜空，知道今夜只能等，样本已离手。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["动机链完整", "收益偏弱但非心理断裂"],
            "required_evidence_region": ["样本", "医馆"],
            "forbidden_diagnoses": ["动机缺口", "缺恐惧来源", "角色链为空"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：心理链闭合，勿误判为角色失败。",
        },
    },
    {
        "case_id": "L2V2-007",
        "target_module": "L2-04",
        "case_type": "A",
        "v1_ref": "L2P-007",
        "failure_type": "创意设定失败",
        "repair_direction": "加压选择",
        "failure_quote": "却无人上前",
        "ir_files": {
            "IR/IR-02_世界约束.md": """# IR-02 世界约束

| 编号 | 规则 | 触发条件 | 代价 | 后果 |
|---|---|---|---|---|
| R-101 | 入塔需持木牌 | 踏入塔门 | 失去一段记忆 | 遗忘重要之人 |""",
        },
        "chapter": """# 段落一

塔院试炼开启。执事宣布：入塔者需持木牌。众人看牌，却无人上前。

# 段落二

木牌在案几摆成一排。有人议论塔内机缘，有人退后半步。执事未说明不取牌有何后果。

# 段落三

执事重复：按牌序进塔。仍无人伸手取牌。烛火在塔门边晃。

# 段落四

风声灌进塔门。学徒问：若不要机缘呢？执事笑而不答，只指木牌。

# 段落五

试炼时辰将尽，仍无一人取牌。塔内机缘被反复提起，却无人做出取舍。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["设定未施压", "规则未逼迫选择", "代价未落地"],
            "required_evidence_region": ["木牌", "试炼"],
            "forbidden_diagnoses": ["设定新奇度", "文风", "事实硬冲突"],
            "expected_reroute": False,
            "minimum_action_requirements": ["加压", "逼迫选择"],
            "human_notes": "A类：IR有代价，正文未推动取牌。",
        },
    },
    {
        "case_id": "L2V2-008",
        "target_module": "L2-04",
        "case_type": "B",
        "v1_ref": "L2P-008",
        "failure_type": "创意设定失败",
        "repair_direction": "加压选择",
        "failure_quote": "必须两人同行",
        "chapter": """# 段落一

边哨夜间换岗。守则写明：凡夜巡者必须两人同行，不得单人离塔。队长在墙上钉了铜牌示警。

# 段落二

新卒问：若一人受伤？守则补：伤者留守，另一人不得折返，须先报号。限制、规则、代价均在一页。

# 段落三

除非持队长印，否则不得开西闸。西闸外是沼泽，开闸需登记。

# 段落四

当夜无异常。新卒与老兵共巡一圈，回报平安。换岗结束，队长收印。

# 段落五

新卒回塔后复述守则两句，老兵点头。西墙脚步一致，铜牌在风里轻响。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["设定简单但完备", "规则限制代价齐全"],
            "required_evidence_region": ["守则", "西闸"],
            "forbidden_diagnoses": ["设定压力不足", "规则缺失", "代价缺失"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：平淡但规则/限制/代价均成立。",
        },
    },
    {
        "case_id": "L2V2-009",
        "target_module": "L2-05",
        "case_type": "A",
        "v1_ref": "L2P-009",
        "failure_type": "E低：即时情绪反馈弱",
        "repair_direction": "前置冲突",
        "failure_quote": "北渡关闭",
        "chapter": """# 段落一

清晨，渡口人群拥挤。公告写：今日不开北渡。无人解释原因，主角在人群里被推搡，不知下一步。

# 段落二

广播通知：北渡关闭。巡逻员又说：北渡已经关闭。核心信息重复，场面仍乱，没有新进展。

# 段落三

中段，主角在工具间找到备用绳梯，却未改变被困处境。人群只是换个方向挤。

# 段落四

日暮，人群散去一半。主角仍不知是否改走南渡。章末没有新问题钩住。

# 段落五

他再次读公告，字句未变。巡逻员口播与广播同句，渡口风硬，他站在原地，决策仍悬着。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["入口弱", "重复兑现", "末段推动力不足", "即时收益弱"],
            "required_evidence_region": ["北渡", "关闭"],
            "forbidden_diagnoses": ["文风", "语气漂移", "事实硬冲突"],
            "expected_reroute": False,
            "minimum_action_requirements": ["前置冲突", "减少重复", "章末钩子"],
            "human_notes": "A类：重复通知+软收束。",
        },
    },
    {
        "case_id": "L2V2-010",
        "target_module": "L2-05",
        "case_type": "B",
        "v1_ref": "L2P-010",
        "failure_type": "E低：即时情绪反馈弱",
        "repair_direction": "前置冲突",
        "failure_quote": "找账本",
        "chapter": """# 段落一

段砺要在乱后清点库房。他骂骂咧咧推开霉味门，动作粗鲁，目标清楚：找账本。

# 段落二

账本在铁柜底层。他撬开柜门，核对编号，记录缺损。骂声粗粝，清点却一项一项落地。

# 段落三

补给处排队漫长，他凭清点单领到盐与布。短缺背景下，他必须完成清点才能领到物资。

# 段落四

段砺把布分给伤员，骂声未停，却完成分配。入口是乱后短缺，中段领到补给，末段承担分配。

# 段落五

伤员道谢，他摆手骂了一句，转身回库房补记最后一页。任务收束，骂声仍旧，动作未停。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["体验成立", "文风粗但非本模块"],
            "required_evidence_region": ["清点", "补给"],
            "forbidden_diagnoses": ["解释腔", "人物语气", "设定压力"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：勿跨域诊断文风。",
        },
    },
    {
        "case_id": "L2V2-011",
        "target_module": "L2-06",
        "case_type": "A",
        "v1_ref": "L2P-011",
        "failure_type": "技术护栏失败",
        "repair_direction": "统一事实",
        "failure_quote": "已在南码头卸货",
        "prior": """# 前序

魏瑾清晨在城北货栈当班。登记簿写：魏瑾位于城北货栈，未离岗。""",
        "ir_files": {"IR/IR-08_状态快照.md": "# IR-08 状态快照\n\n魏瑾位于城北货栈。"},
        "chapter": """# 段落一

魏瑾在城北货栈核对封条。封条完好，他记录编号，准备交接。同页后文写：魏瑾已在南码头卸货。

# 段落二

两份记录同一时刻。城北当班员说魏瑾未离工位，码头值班却说魏瑾已签卸货单。

# 段落三

魏瑾本人沉默，只把两份记录并排放。两份记录并排，间隔处空白。

# 段落四

货栈主管要求停交接，码头催继续卸货。读者面对同一人物、同一时刻、两处位置。

# 段落五

风把码头旗吹向城北。魏瑾仍不说话，只让旁人自行比对两份记录。""",
        "expected": {
            "expected_issue_present": True,
            "acceptable_root_causes": ["事实冲突", "位置互斥", "双来源不一致"],
            "required_evidence_region": ["城北", "城南", "魏瑾"],
            "forbidden_diagnoses": ["ALLOWED_CHANGE", "文风"],
            "expected_reroute": False,
            "minimum_action_requirements": ["对齐位置事实"],
            "human_notes": "A类：同时声明城北与城南，无时间桥梁。",
        },
    },
    {
        "case_id": "L2V2-012",
        "target_module": "L2-06",
        "case_type": "B",
        "v1_ref": "L2P-012",
        "failure_type": "技术护栏失败",
        "repair_direction": "统一事实",
        "failure_quote": "左臂已经痊愈",
        "prior": """# 前序

清晨，温屿仍在东岸营地，左臂以布条吊着，伤处渗血。""",
        "chapter": """# 段落一

清晨，温屿仍在东岸营地，左臂以布条吊着，伤处渗血。他记录潮汐表，动作受限。

# 段落二

数日后，温屿左臂已经痊愈，他在西岸修补缆绳。时间翻过数日，场景换到西岸缆绳边。

# 段落三

同伴问：臂伤怎么好的？温屿答：军医换了药，禁练三日。变化有说明，动作从受限到利落。

# 段落四

西岸缆绳老旧，他换结法。伤愈与地点转移均有交代，记录写：伤愈后可归队。

# 段落五

日暮收工，温屿把药棉收好。东岸营地与西岸缆绳场景切换，均有叙事过渡。""",
        "expected": {
            "expected_issue_present": False,
            "acceptable_root_causes": ["ALLOWED_CHANGE", "合法状态变化", "时间跨度解释充分"],
            "required_evidence_region": ["伤", "痊愈", "数日后"],
            "forbidden_diagnoses": ["HARD_CONFLICT", "硬冲突"],
            "expected_reroute": True,
            "minimum_action_requirements": [],
            "human_notes": "B类：数日后伤愈，不得判硬冲突。",
        },
    },
]


def _build_failure_item(case: dict[str, Any], chapter_body: str) -> dict[str, Any]:
    quote = case["failure_quote"]
    paragraphs = segment_paragraphs(chapter_body)
    para = paragraph_for_quote(paragraphs, quote)
    if para is None:
        raise ValueError(f"{case['case_id']}: failure_quote not found: {quote}")
    return {
        "来源闸门": "L1-01",
        "名称": case["case_id"],
        "状态": "失败",
        "说明": f"{case['case_id']} v2 corpus",
        "证据": [{"段落": para, "摘句": quote}],
        "严重级别": "error",
        "失败类型": case["failure_type"],
        "候选模块": case["target_module"],
        "回流验收位置": "L1-01",
        "修复方向": case["repair_direction"],
    }


def _audit_v1_case(entry: dict[str, Any]) -> dict[str, Any]:
    auto = validate_case(V1, entry)
    case_id = entry["case_id"]
    human = V1_HUMAN_AUDIT[case_id]
    body = clean_body(
        (V1 / entry["case_dir"] / "chapters" / "chapter.md").read_text(encoding="utf-8")
    )
    leakage = bool(auto["leakage_hits"]) or bool(scan_patterns(body, LEAKAGE_PATTERNS))
    meta = bool(auto["meta_hits"]) or bool(scan_patterns(body, META_PATTERNS))
    filler = bool(auto["filler_hits"])
    ev_loc = bool(auto["evidence_results"])
    for e in auto["evidence_results"]:
        if not e.get("quote_found") or not e.get("paragraph_match"):
            ev_loc = False
    return {
        "case_id": case_id,
        "module_id": entry["target_module"],
        "case_type": entry["case_type"],
        "leakage_found": leakage,
        "meta_text_found": meta,
        "filler_found": filler,
        "evidence_location_valid": ev_loc,
        "evidence_semantically_valid": None,
        "naturalness": "FAIL" if (leakage or meta or filler) else "REVIEW",
        "case_type_valid": "FAIL" if leakage else "REVIEW",
        "decisive_findings": auto["leakage_hits"][:5] + auto["meta_hits"][:3] + auto["filler_hits"][:2],
        "required_action": human["required_action"],
        "final_status": human["final_status"],
        "corpus_status_label": human.get("corpus_status_label"),
        "automated_errors": auto["errors"],
    }


def write_v1_audit() -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    results = [_audit_v1_case(e) for e in manifest["cases"]]
    payload = {
        "schema_version": "xcue.l2-corpus-audit/1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "l2_real_api_pilot v1",
        "status": {
            "L2_R5C_FULL_PROTOCOL": "PASSED",
            "R5D_BUSINESS_REVIEW": "PAUSED",
            "R5D_CORPUS_AUDIT": "PASSED",
            "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
        },
        "counts": {
            "VALID": sum(1 for r in results if r["final_status"] == "VALID"),
            "REPAIR_REQUIRED": sum(1 for r in results if r["final_status"] == "REPAIR_REQUIRED"),
            "INVALID_REPLACE": sum(1 for r in results if r["final_status"] == "INVALID_REPLACE"),
        },
        "cases": results,
    }
    (AUDIT_DIR / "12例审计结果.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["# 12 例 v1 语料审计结果", "", f"生成时间：{payload['generated_at']}", ""]
    for row in results:
        lines.append(f"## {row['case_id']} ({row['module_id']} {row['case_type']})")
        lines.append(f"- 状态：**{row['final_status']}**")
        lines.append(f"- 泄露：{row['leakage_found']} | 元叙述：{row['meta_text_found']} | 填充：{row['filler_found']}")
        lines.append(f"- 证据位置有效：{row['evidence_location_valid']}")
        lines.append(f"- 处置：{row['required_action']}")
        lines.append("")
    (AUDIT_DIR / "12例审计结果.md").write_text("\n".join(lines), encoding="utf-8")

    invalid = [r for r in results if r["final_status"] == "INVALID_REPLACE"]
    repair = [r for r in results if r["final_status"] == "REPAIR_REQUIRED"]
    valid = [r for r in results if r["final_status"] == "VALID"]
    (AUDIT_DIR / "无效案例清单.md").write_text(
        "\n".join([f"- {r['case_id']}: {r['required_action']}" for r in invalid]) or "- 无",
        encoding="utf-8",
    )
    (AUDIT_DIR / "可修复案例清单.md").write_text(
        "\n".join([f"- {r['case_id']}: {r['required_action']}" for r in repair]) or "- 无",
        encoding="utf-8",
    )
    (AUDIT_DIR / "有效案例清单.md").write_text(
        "\n".join([f"- {r['case_id']}" for r in valid]) or "- 无",
        encoding="utf-8",
    )

    leak_lines = ["# 泄露语句定位表", ""]
    for row in results:
        leak_lines.append(f"## {row['case_id']}")
        for hit in row.get("decisive_findings") or []:
            leak_lines.append(f"- {hit}")
        leak_lines.append("")
    (AUDIT_DIR / "泄露语句定位表.md").write_text("\n".join(leak_lines), encoding="utf-8")

    (AUDIT_DIR / "语料审计说明.md").write_text(
        "\n".join(
            [
                "# R5D 语料质量审计说明",
                "",
                "v1 12 例均不适合继续用于 R5D 人工业务评分。",
                "",
                "## 状态",
                "",
                "- `L2_R5C_FULL_PROTOCOL = PASSED`（保留）",
                "- `R5D_BUSINESS_REVIEW = PAUSED`",
                "- `R5D_CORPUS_AUDIT = PASSED`",
                "- `L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED`",
                "",
                "## 统计",
                "",
                f"- VALID: {payload['counts']['VALID']}",
                f"- REPAIR_REQUIRED: {payload['counts']['REPAIR_REQUIRED']}",
                f"- INVALID_REPLACE: {payload['counts']['INVALID_REPLACE']}",
                "",
                "干净语料见 `tests/fixtures/l2_real_api_pilot_v2/`。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def write_v2() -> None:
    V2.mkdir(parents=True, exist_ok=True)
    (V2 / "cases").mkdir(exist_ok=True)
    (V2 / "expected").mkdir(exist_ok=True)
    (V2 / "results").mkdir(exist_ok=True)

    manifest_cases = []
    for case in V2_CASES:
        case_id = case["case_id"]
        case_dir = V2 / "cases" / case_id
        (case_dir / "chapters").mkdir(parents=True, exist_ok=True)
        chapter_path = case_dir / "chapters" / "chapter.md"
        chapter_path.write_text(case["chapter"].strip() + "\n", encoding="utf-8")
        body = clean_body(case["chapter"])
        failure_item = _build_failure_item(case, body)
        (case_dir / "failure_item.json").write_text(
            json.dumps(failure_item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        project = {
            "schema_version": "xcue.project-manifest/1.0",
            "project_id": case_id,
            "content_root": "chapters",
            "default_chapter": "chapters/chapter.md",
            "entrypoint": "chapters/chapter.md",
            "entrypoint_type": "pilot",
        }
        if case.get("ir_files"):
            project["required_dirs"] = ["IR"]
        if case.get("prior"):
            project["chapter_sequence"] = ["chapters/prior.md", "chapters/chapter.md"]
        (case_dir / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        if case.get("prior"):
            (case_dir / "chapters" / "prior.md").write_text(case["prior"].strip() + "\n", encoding="utf-8")
        for rel, content in (case.get("ir_files") or {}).items():
            path = case_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content.strip() + "\n", encoding="utf-8")
        expected = {
            "case_id": case_id,
            "target_module": case["target_module"],
            "case_type": case["case_type"],
            **case["expected"],
        }
        (V2 / "expected" / f"{case_id}.expected.json").write_text(
            json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest_cases.append(
            {
                "case_id": case_id,
                "target_module": case["target_module"],
                "case_type": case["case_type"],
                "case_dir": f"cases/{case_id}",
                "v1_ref": case["v1_ref"],
            }
        )

    manifest = {
        "schema_version": "xcue.l2-real-api-pilot/2.0",
        "pilot_id": "L2_REAL_API_PILOT_V2",
        "status": "READY",
        "case_count": 12,
        "cases": manifest_cases,
    }
    (V2 / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (V2 / "README.md").write_text(
        "\n".join(
            [
                "# L2 Real API Pilot v2",
                "",
                "干净业务评测语料，独立于 v1。",
                "",
                "校验：`python 脚本/校验_L2_业务评测语料.py --dataset-v2`",
                "",
                "不得覆盖 v1 或 R5A～R5C 历史结果。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def pause_r5d_review() -> None:
    if R5D_DIR.is_dir():
        summary_path = R5D_DIR / "人工评分汇总.json"
        if summary_path.is_file():
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            data["status"] = "PAUSED_CORPUS_AUDIT"
            data["labels"] = {
                "R5D_BUSINESS_REVIEW": "WAITING_FOR_V2_API_RUN",
                "R5D_CORPUS_AUDIT": "PASSED",
                "L2_R5D_BUSINESS_PILOT": "PAUSED",
                "L2_REAL_MODEL_EFFECTIVENESS": "NOT_TESTED",
                "PRODUCTION_ELIGIBLE": False,
            }
            data["pause_reason"] = "v1 语料存在答案泄露与元叙述，改用 l2_real_api_pilot_v2"
            summary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    audit = write_v1_audit()
    write_v2()
    pause_r5d_review()
    v2_report = validate_dataset(V2)
    print(f"V1 audit: INVALID_REPLACE={audit['counts']['INVALID_REPLACE']}")
    print(f"V2 validation: {'OK' if v2_report['validation_ok'] else 'FAIL'}")
    if not v2_report["validation_ok"]:
        for c in v2_report["cases"]:
            if c["errors"]:
                print(c["case_id"], c["errors"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
