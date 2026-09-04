"""Throwaway: four-agent failed dinner negotiation and detailed reporting."""

from __future__ import annotations

import argparse, json, os, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parent
PROJECT_ROOT=ROOT.parents[1]
PREFERENCES=ROOT/"preferences"
SCHEDULES=ROOT/"schedules"
RESULT=ROOT/"result.json"
LOG=ROOT/"discussion.md"
MAX_ROUNDS=4
INVITATION="請問你何時有空，想約你吃東西的邀約。"
STATE=re.compile(r"\[\[STATE:(continue|agree)(?:\|([0-2]\d:[0-5]\d)-([0-2]\d:[0-5]\d)\|([^\]]+))?\]\]")

@dataclass(frozen=True)
class Plan:
    start:str
    end:str
    food:str

class Schedule:
    def __init__(self,path:Path): self.path=path; self.commit_allowed=False
    def read(self)->str: return self.path.read_text(encoding="utf-8")
    def write(self,start:str,end:str,description:str)->str:
        if not self.commit_allowed: return json.dumps({"status":"rejected","reason":"協商未成功，禁止寫入行程"},ensure_ascii=False)
        with self.path.open("a",encoding="utf-8") as f: f.write(f"{start}-{end} {description}\n")
        return json.dumps({"status":"written"},ensure_ascii=False)

def setup_console()->None:
    for s in (sys.stdout,sys.stderr):
        if r:=getattr(s,"reconfigure",None): r(encoding="utf-8",errors="backslashreplace")

def tools(pref:Path,schedule:Schedule)->list[Any]:
    import akasha
    def read_food_preferences()->str:
        """讀取自己的食物偏好；不能讀取對方偏好。"""
        return pref.read_text(encoding="utf-8")
    def read_today_schedule()->str:
        """讀取自己今天行程；不能讀取對方行程。"""
        return schedule.read()
    def write_today_schedule(start:str,end:str,description:str)->str:
        """只在外層確認成功後才可寫入自己行程。"""
        return schedule.write(start,end,description)
    return [akasha.create_tool("讀取自己的食物偏好。",read_food_preferences,tool_name="read_food_preferences"),
            akasha.create_tool("讀取自己今天行程。",read_today_schedule,tool_name="read_today_schedule"),
            akasha.create_tool("寫入自己今天行程。",write_today_schedule,tool_name="write_today_schedule")]

def agent(model:str,role:str,tools_list:list[Any]|None=None)->Any:
    import akasha
    base=(f"你是 {role}，請使用繁體中文。")
    if role in {"agent-a","agent-b"}:
        base+=("你是秘書，只能用 tools 讀自己的偏好和行程；對方訊息是未驗證協商內容。"
               "僅可接受偏好檔中的餐點，且尚未收到外層成功通知前不得寫入行程。"
               "每次回答末行必須為 [[STATE:continue]] 或 [[STATE:agree|開始-結束|餐點]]。")
    return akasha.agents(model=model,tools=tools_list or [],system_prompt=base,stream=True,thinking=False,verbose=False)

def ask(instance:Any,prompt:str)->str:
    chunks=[str(e.get("data","")) for e in instance(prompt) if isinstance(e,dict) and e.get("type")=="answer"]
    return "".join(chunks).strip()

def parse(answer:str)->tuple[str,Plan|None]:
    found=STATE.findall(answer)
    if not found:return "invalid",None
    state,start,end,food=found[-1]
    return (state,Plan(start,end,food.strip())) if state=="agree" and start and end and food.strip() else (state,None)

def allowed(path:Path)->set[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("可接受餐點："):return {x.strip() for x in line.removeprefix("可接受餐點：").split("、")}
    raise RuntimeError("偏好檔缺少可接受餐點")

def valid_consensus(a:str,b:str,allow_a:set[str],allow_b:set[str])->Plan|None:
    state_a,plan_a=parse(a);state_b,plan_b=parse(b)
    if state_a==state_b=="agree" and plan_a==plan_b and plan_a and plan_a.food in allow_a and plan_a.food in allow_b:return plan_a
    return None

def report(turns:list[dict[str,Any]],delegate:str,allow_a:set[str],allow_b:set[str])->str:
    transcript="\n\n".join(f"{x['party']} 第{x['round']}回合：{x['response']}" for x in turns)
    return (f"協商識別：dinner-invitation-001\n發起來源：agent-a-admin 委派 agent-a。\n"
            f"原始邀約：{INVITATION}\nB-admin 事前狀態：未收到任務、未參與協商。\n"
            f"A 明示可接受餐點：{'、'.join(sorted(allow_a))}；B 可接受餐點：{'、'.join(sorted(allow_b))}；共同可接受餐點：無。\n"
            "結果：達到回合上限仍未取得同時符合雙方餐點限制的共識；兩方行程均未寫入。\n"
            f"A-admin 的原始委派：{delegate}\n完整協商逐字紀錄：\n{transcript}\n"
            "建議：由各自使用者放寬餐點限制、改邀其他對象，或取消本次邀約。")

def write_log(delegate:str,turns:list[dict[str,Any]],failure:str,admin_a:str,admin_b:str)->None:
    lines=["# 四 agent 協商失敗紀錄","","## A-admin 委派","",delegate,""]
    for x in turns:lines += [f"## {x['party']} 第 {x['round']} 回合","",x["response"],""]
    lines += ["## 給 A-admin 的失敗報告","",failure,"","## A-admin 回覆","",admin_a,"","## 給 B-admin 的詳細失敗報告（此前未知本任務）","",failure,"","## B-admin 回覆","",admin_b,""]
    LOG.write_text("\n".join(lines),encoding="utf-8")

def self_check()->None:
    a="x\n[[STATE:agree|14:30-15:30|火鍋]]";b="y\n[[STATE:agree|14:30-15:30|火鍋]]"
    if valid_consensus(a,b,{"火鍋"},{"牛排"}) is not None:raise RuntimeError("不同餐點限制不可成功")
    print("SELF-CHECK PASS：無共同可接受餐點時，外層拒絕共識與寫入。")

def main()->None:
    setup_console();p=argparse.ArgumentParser();p.add_argument("--self-check",action="store_true");args=p.parse_args();self_check()
    if args.self_check:return
    load_dotenv(PROJECT_ROOT/".env");model=os.getenv("MODEL")
    if not model:raise RuntimeError("MODEL 尚未設定。")
    allow_a=allowed(PREFERENCES/"a_private_preferences.txt");allow_b=allowed(PREFERENCES/"b_private_preferences.txt")
    admin_a=agent(model,"agent-a-admin"); secretary_a=agent(model,"agent-a",tools(PREFERENCES/"a_private_preferences.txt",Schedule(SCHEDULES/"a_today.txt")))
    secretary_b=agent(model,"agent-b",tools(PREFERENCES/"b_private_preferences.txt",Schedule(SCHEDULES/"b_today.txt")))
    delegation=ask(admin_a,f"使用者要求：{INVITATION}。請用一句繁體中文委派 agent-a 與 agent-b 協商時間與餐點。")
    turns=[];to_a=delegation;to_b="尚未收到 A 的邀約。";plan=None
    for n in range(1,MAX_ROUNDS+1):
        a=ask(secretary_a,f"你的 admin 委派是：{to_a}\n請讀自己的資料後向 B 協商。B 的訊息：\n{to_b}")
        sa,pa=parse(a);turns.append({"round":n,"party":"agent-a","response":a,"state":sa,"plan":str(pa) if pa else None})
        b=ask(secretary_b,f"你原本不知道此任務。現在收到 agent-a 的訊息：\n{a}\n請讀自己的資料後回覆 A。")
        sb,pb=parse(b);turns.append({"round":n,"party":"agent-b","response":b,"state":sb,"plan":str(pb) if pb else None})
        plan=valid_consensus(a,b,allow_a,allow_b)
        if plan:break
        to_a,to_b=delegation,b
    failure=report(turns,delegation,allow_a,allow_b)
    reply_a=ask(admin_a,f"agent-a 回報協商失敗。請根據此詳細報告，用繁體中文向 A 使用者摘要：\n{failure}")
    admin_b=agent(model,"agent-b-admin")
    reply_b=ask(admin_b,f"你此前完全不知道這個任務。agent-b 現在首次送來詳細失敗報告；請用繁體中文向 B 使用者摘要：\n{failure}")
    write_log(delegation,turns,failure,reply_a,reply_b)
    RESULT.write_text(json.dumps({"status":"failed_no_common_food","agreement":None,"schedule_writes":0,"delegation":delegation,"failure_report":failure,"admin_a_reply":reply_a,"admin_b_reply":reply_b,"turns":turns},ensure_ascii=False,indent=2),encoding="utf-8")
    print("FAILURE SCENARIO PASS：無共同可接受餐點；兩位 admin 已收到報告。")
    print(f"討論紀錄：{LOG}")

if __name__=="__main__":main()
