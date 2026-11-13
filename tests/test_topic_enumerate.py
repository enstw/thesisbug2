"""topic-enumerate: the owner steers, the ledger keeps every pair and every answer honest."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "topic-enumerate.py"
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location("topic_enumerate", SCRIPT)
te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(te)

ANCHOR = """# 選題定錨

<!-- 這段註解不該進 prompt -->

## 領域

虛構學門的虛構次領域

## 現象

某虛構城市在 2031 年推行的虛構登記制度

## 可得資料

只有主人知道的資料來源

## 指導與限制

只有主人知道的指導限制
"""

MATERIAL = """---
title: 虛構日報的報導
source: 虛構日報
note: 不該進 prompt 的前言
---

# 虛構報導

第一段：登記變嚴格之後，申請人等待的時間變長。

第二段：承辦人說規則越細，越難照個案調整。

## 小標

第三段：主管機關宣稱兩者可以兼得。
"""


def topic(**over):
    base = {"question": "為何登記越嚴格，等待越久？", "type": "解釋", "improves": "甲",
            "scope": "某虛構城市的申請人", "data": "申請紀錄", "why": "第一段的事實",
            "passages": ["M01-P001"]}
    base.update(over)
    return base


def refined(**over):
    base = {k: v for k, v in topic().items() if k not in ("type", "improves")}
    base.update(over)
    return base


def rows(count, kind="無矛盾", **special):
    """An answer with no topic anywhere, except the rows given as n1=…, n2=…"""
    out = [{"n": n, "topics": [], "none": kind, "reason": "兩者互不影響"} for n in range(1, count + 1)]
    for n, row in special.items():
        out[int(n[1:]) - 1] = row
    return {"rows": [r for r in out if r is not None]}


class PureTests(unittest.TestCase):
    def test_parameter_file_has_39_complete_rows_in_five_groups(self):
        params = te.load_params()["parameters"]
        self.assertEqual([p["n"] for p in params], list(range(1, 40)))
        self.assertEqual(len({p["group"] for p in params}), 5)
        for p in params:
            for field in ("group", "triz", "analogy", "examples"):
                self.assertTrue(p[field].strip(), (p["n"], field))

    def test_every_pair_exists_once(self):
        pairs = te.all_pairs(39)
        self.assertEqual((len(pairs), len(set(pairs))), (741, 741))

    def test_passages_skip_front_matter_and_headings(self):
        blocks = te.split_passages(MATERIAL)
        self.assertEqual([b[1][:3] for b in blocks if not b[2]], ["第一段", "第二段", "第三段"])
        self.assertEqual([b[0] for b in blocks if not b[2]], [9, 11, 15])


    def test_fetched_transcripts_lose_capture_notes_and_front_matter(self):
        text = ("<!-- 擷取：某工具，2031-01-01；\n付費牆截斷 -->\n---\ntitle: 某報導\nsitename: 某報\n"
                'date: "2031-01-02"\ntags: [\'x\']\n---\n## 小標\n\n內文一段。\n')
        lines, meta = te.content_lines(text)
        self.assertEqual((meta["title"], meta["sitename"], meta["date"]), ("某報導", "某報", "2031-01-02"))
        self.assertEqual([(b[0], b[1]) for b in te.split_passages(text) if not b[2]], [(11, "內文一段。")])


class RunCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.unit = self.root / "units" / "01-preparation-topic"
        self.unit.mkdir(parents=True)
        (self.unit / "WORK.json").write_text('{"type": "preparation"}', encoding="utf-8")
        self.base = self.unit / "topic-enum"
        self.run_dir = self.base / "runs" / "r1"

    def fw(self, *args):
        env = dict(os.environ, FW_COURSE_ROOT=str(self.root))
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root, env=env,
                              capture_output=True, text=True, timeout=120)

    def ok(self, *args):
        r = self.fw(*args)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def state(self):
        return json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))

    def start(self, *extra):
        """A run already searching, where one button press sends one prompt unless a test asks for more."""
        self.prepare()
        self.ok("start", "topic", "--seed", "7", "--fan", "1", *extra)
        self.ok("choose", "topic", "begin")

    def prepare(self):
        (self.base / "materials").mkdir(parents=True)
        (self.base / "anchor.md").write_text(ANCHOR, encoding="utf-8")
        (self.base / "materials" / "news.md").write_text(MATERIAL, encoding="utf-8")

    def tasks(self, *flags):
        r = self.ok("next", "topic", "--wait", "0", *flags)
        return [{k: v.strip() for k, v in (line.split(":", 1) for line in block.splitlines())}
                for block in r.stdout.strip().split("\n\n")]

    def answer(self, data, task=None):
        task = task or self.tasks()[0]
        (self.root / task["answer"]).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return self.fw("take", "topic")

    def found_topic(self):
        """Explore once and get one topic on the first pair."""
        self.start()
        self.ok("choose", "topic", "explore")
        r = self.answer(rows(5, n1={"n": 1, "topics": [topic()]}))
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.state()["topics"][0]


class RunTests(RunCase):
    def test_begin_needs_a_filled_anchor_and_a_material_with_text(self):
        self.ok("init", "topic")
        self.ok("start", "topic", "--stock-examples")
        self.assertIn("「領域」還沒填", self.fw("choose", "topic", "begin").stderr)
        self.assertIn("「現象」裡還有〔〕要補", self.fw("choose", "topic", "anchor").stderr)
        (self.base / "anchor.md").write_text(ANCHOR, encoding="utf-8")
        self.ok("choose", "topic", "anchor")
        self.assertEqual(self.state()["stage"], "materials")
        self.assertIn("至少要勾選一份", self.fw("choose", "topic", "begin").stderr)
        self.assertFalse((self.run_dir / "passages.json").exists())

    def test_a_run_keeps_what_it_started_with(self):
        self.start()
        first = self.state()
        self.assertEqual((len(first["order"]), len(set(first["order"]))), (741, 741))
        r = self.fw("start", "topic", "--seed", "8")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--run", r.stderr)
        self.assertEqual(self.state(), first)
        self.ok("start", "topic", "--seed", "7", "--run", "r2")
        again = json.loads((self.base / "runs" / "r2" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(again["order"], first["order"])
        self.assertIn("不能再改", self.fw("choose", "topic", "anchor").stderr)
        self.assertIn("不能再改", self.fw("choose", "topic", "use", "M01", "--off").stderr)

    def test_nothing_is_sent_until_the_owner_presses_a_button(self):
        self.start()
        r = self.fw("next", "topic", "--wait", "0")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.state()["tasks"], [])

    def test_prompt_carries_what_helps_and_nothing_else(self):
        self.start()
        self.ok("choose", "topic", "explore", "--group", "信任與風險")
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T001 explore")
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        for wanted in ("虛構學門的虛構次領域", "某虛構城市在 2031 年推行的虛構登記制度",
                       "[M01-P001] 第一段", "[M01-P003] 第三段", "### 材料 1：虛構日報的報導", "〈虛構報導〉",
                       "5. 甲：",
                       str(self.run_dir / "answers" / "T001.json")):
            self.assertIn(wanted, prompt)
        self.assertEqual(task["answer"], str(self.run_dir / "answers" / "T001.json"))
        for leaked in ("只有主人知道", "這段註解", "不該進 prompt 的前言", "TRIZ", "切片", "信任與風險",
                       "移動物體", "參數", "materials/news.md", "{{"):
            self.assertNotIn(leaked, prompt)
        self.assertNotIn("6. 甲：", prompt)
        by_n = te.load_params()["by_n"]
        for a, b in self.state()["tasks"][0]["items"]:
            self.assertIn("信任與風險", (by_n[a]["group"], by_n[b]["group"]))
        self.assertEqual(self.fw("next", "topic", "--wait", "0").returncode, 3)
        self.assertEqual(self.tasks("--resend"), [task])

    def test_one_press_sends_several_prompts_over_different_pairs(self):
        self.start("--fan", "3", "--limit", "4")
        self.ok("choose", "topic", "explore")
        first = self.tasks()
        self.assertEqual([t["task"] for t in first], ["T001 explore", "T002 explore", "T003 explore"])
        self.ok("choose", "topic", "explore", "--group", "資源與成本")
        r = self.fw("choose", "topic", "explore")
        self.assertIn("已經有 6 份在進行", r.stderr)
        pairs = [te.pair_id(a, b) for t in self.state()["tasks"] for a, b in t["items"]]
        self.assertEqual((len(pairs), len(set(pairs))), (30, 30))

        r = self.answer(rows(5, n2={"n": 2, "topics": [topic()]}), first[1])
        self.assertIn("T002: accepted, 1 topic(s)", r.stdout)
        self.assertIn("still out: T001 T003", r.stdout)
        self.assertEqual([t["task"] for t in self.tasks()], ["T004 explore", "T005 explore", "T006 explore"])

    def test_take_rejects_answers_that_break_the_contract_and_keeps_the_prompt_open(self):
        self.start()
        self.ok("choose", "topic", "explore")
        (task,) = self.tasks()
        cases = [
            (rows(5, n3=None), "no row for 3"),
            (rows(5, n1={"n": 1, "topics": [topic(passages=["M01-P099"])]}), "passages not in the materials: M01-P099"),
            ({"rows": rows(5)["rows"] + [{"n": 6, "topics": [], "none": "無矛盾", "reason": "x"}]}, "not one of the 5"),
            (rows(5, n2={"n": 2, "topics": []}), "reason must say why"),
            (rows(5, n2={"n": 2, "topics": [], "none": "已有人研究", "reason": "x"}), "none must be one of"),
            (rows(5, n1={"n": 1, "topics": [topic(passages=[])]}), "at least one passage"),
            (rows(5, n1={"n": 1, "topics": [topic(type="預測", improves="丙", why=" ")]}), "type must be one of"),
        ]
        for data, message in cases:
            r = self.answer(data, task)
            self.assertEqual(r.returncode, 1, message)
            self.assertIn(message, r.stderr)
            self.assertIn("send units/01-preparation-topic/topic-enum/runs/r1/tasks/T001.md again", r.stderr)
        again = self.fw("take", "topic")
        self.assertEqual((again.returncode, again.stderr), (0, ""))
        state = self.state()
        self.assertEqual((len(state["tasks"]), state["tasks"][0]["status"], state["visited"]), (1, "sent", {}))

    def test_take_refuses_a_prompt_edited_after_it_was_written(self):
        self.start()
        self.ok("choose", "topic", "explore")
        (task,) = self.tasks()
        with (self.root / task["prompt"]).open("a", encoding="utf-8") as f:
            f.write("\n改過\n")
        r = self.answer(rows(5), task)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("was changed after it was written", r.stderr)

    def test_a_draw_that_finds_nothing_is_repeated_until_a_topic_turns_up(self):
        self.start()
        self.ok("choose", "topic", "explore")
        r = self.answer(rows(5, kind="材料無依據"))
        self.assertIn("round 1 found nothing; drew 1 more prompt(s)", r.stdout)
        r = self.answer(rows(5, n4={"n": 4, "topics": [topic(improves="乙")]}))
        self.assertIn("T002: accepted, 1 topic(s)", r.stdout)
        self.assertIn("10/741 pairs read, 1 topic(s); nothing out", r.stdout)
        state = self.state()
        self.assertEqual([t["items"] for t in state["tasks"]],
                         [[list(te.pair_of(p)) for p in state["order"][i:i + 5]] for i in (0, 5)])
        a, b = state["tasks"][1]["items"][3]
        found = state["topics"][0]
        self.assertEqual((found["id"], found["improves"], found["worsens"], found["pair"]),
                         ("Q001", b, a, te.pair_id(a, b)))
        self.assertEqual(sorted({v["result"] for v in state["visited"].values()}), ["材料無依據", "無矛盾", "題目"])
        self.assertEqual(self.fw("next", "topic", "--wait", "0").returncode, 3)

    def test_deepen_holds_one_dimension_and_reads_only_unseen_pairs(self):
        found = self.found_topic()
        focus = found["improves"]
        self.ok("choose", "topic", "deepen", "Q001", "--dimension", str(focus))
        first, second = self.tasks()
        self.assertEqual((first["task"], second["task"]), ("T002 deepen", "T003 deepen"))
        state = self.state()
        items = state["tasks"][1]["items"] + state["tasks"][2]["items"]
        self.assertEqual(len(items), 10)
        self.assertEqual({a for a, _ in items}, {focus})
        self.assertFalse({te.pair_id(a, b) for a, b in items} & set(state["visited"]))
        r = self.answer(rows(5, n2={"n": 2, "topics": [topic(), topic(type="條件")]}), first)
        self.assertIn("T002: accepted, 2 topic(s)", r.stdout)
        self.assertIn("這個面向不屬於這個題目",
                      self.fw("choose", "topic", "deepen", "Q001", "--dimension", "99").stderr)

    def test_vary_and_split_keep_the_contradiction_and_run_once(self):
        found = self.found_topic()
        self.ok("choose", "topic", "vary", "Q001")
        self.assertIn("已經做過了", self.fw("choose", "topic", "vary", "Q001").stderr)
        self.ok("choose", "topic", "split", "Q001")
        vary, split = self.tasks()
        prompt = (self.root / vary["prompt"]).read_text(encoding="utf-8")
        self.assertIn("研究問題：為何登記越嚴格，等待越久？", prompt)
        self.assertNotIn("**解釋**", prompt)
        for kind in ("描述", "條件", "評估"):
            self.assertIn(f"**{kind}**", prompt)
        self.assertIn("none must be one of", self.answer(rows(3, kind="無矛盾"), vary).stderr)
        data = rows(3, kind="不適用", n2={"n": 2, "topics": [refined(question="在何種條件下不會變久？")]})
        self.assertEqual(self.answer(data, vary).returncode, 0)
        child = self.state()["topics"][1]
        self.assertEqual((child["id"], child["parent"], child["type"], child["improves"], child["worsens"]),
                         ("Q002", "Q001", "條件", found["improves"], found["worsens"]))
        self.assertIn("本身就是變化出來的", self.fw("choose", "topic", "vary", "Q002").stderr)

        data = rows(4, kind="材料無依據", n3={"n": 3, "topics": [refined(scope="只看新申請人")]})
        self.assertEqual(self.answer(data, split).returncode, 0)
        state = self.state()
        part = state["topics"][2]
        self.assertEqual((part["parent"], part["axis"], part["type"], part["scope"]),
                         ("Q001", "對象", "解釋", "只看新申請人"))
        self.assertEqual(len(state["visited"]), 5)

    def test_drawer_collects_topics_and_finish_ends_the_run(self):
        self.found_topic()
        self.assertIn("找不到這個題目", self.fw("choose", "topic", "keep", "Q009").stderr)
        self.ok("choose", "topic", "keep", "Q001")
        self.ok("choose", "topic", "keep", "Q001")
        self.assertEqual(self.state()["drawer"], ["Q001"])
        self.ok("choose", "topic", "vary", "Q001")
        self.assertEqual(self.answer(rows(3, kind="不適用", n2={"n": 2, "topics": [
            refined(question="在何種條件下不會變久？")]})).returncode, 0)
        found = self.state()["topics"][0]
        by_n = te.load_params()["by_n"]
        out = self.ok("shortlist", "topic").stdout
        for wanted in ("| Q001（題名待定） | 為何登記越嚴格，等待越久？ | 待查 | 待查 | 待查 |",
                       "## Q001 為何登記越嚴格，等待越久？",
                       "- **題型**：解釋。研究設計偏向機制",
                       f"- **核心矛盾**：改善「{by_n[found['improves']]['analogy']}」會惡化「{by_n[found['worsens']]['analogy']}」",
                       "  - `M01-P001` 虛構日報的報導（虛構日報）：第一段：登記變嚴格之後，申請人等待的時間變長。",
                       "  - Q002 條件：在何種條件下不會變久？（沒放進抽屜）",
                       "- **可得資料**：只有主人知道的資料來源"):
            self.assertIn(wanted, out)
        self.ok("choose", "topic", "drop", "Q001")
        self.assertEqual(self.state()["drawer"], [])
        self.ok("choose", "topic", "finish")
        self.assertEqual(self.fw("next", "topic", "--wait", "0").returncode, 5)
        self.assertIn("這一輪已經結束", self.fw("choose", "topic", "explore").stderr)


    def test_cancel_withdraws_prompts_and_frees_their_pairs_and_buttons(self):
        self.found_topic()
        self.assertIn("沒有進行中的工作", self.fw("choose", "topic", "cancel").stderr)
        self.ok("choose", "topic", "explore")
        self.ok("choose", "topic", "vary", "Q001")
        sent = self.tasks()
        held = self.state()["tasks"][1]["items"]
        self.ok("choose", "topic", "split", "Q001")
        self.ok("choose", "topic", "cancel")
        self.assertEqual(self.tasks(), [{"stop": "T002 T003"}])
        self.assertEqual(self.fw("next", "topic", "--wait", "0").returncode, 3)
        r = self.answer(rows(5, n1={"n": 1, "topics": [topic()]}), sent[0])
        self.assertIn("5/741 pairs read, 1 topic(s); nothing out", r.stdout)
        state = self.state()
        self.assertEqual([t["status"] for t in state["tasks"]], ["done", "cancelled", "cancelled", "cancelled"])
        self.assertEqual((state["topics"][0]["done"], state["rounds"][1]["closed"]), ([], True))
        self.ok("choose", "topic", "vary", "Q001")
        self.ok("choose", "topic", "explore")
        self.assertEqual(self.state()["tasks"][5]["items"], held)

    def test_search_stops_to_ask_after_empty_draws_in_a_row(self):
        self.start()
        self.ok("choose", "topic", "explore", "--group", "信任與風險")
        self.answer(rows(5, kind="材料無依據"))
        r = self.answer(rows(5, n2={"n": 2, "topics": [], "none": "無矛盾", "reason": "互不影響"}, kind="材料無依據"))
        self.assertIn("2 draws in a row found nothing; stopped", r.stdout)
        state = self.state()
        self.assertEqual(len(state["tasks"]), 2)
        self.assertEqual(state["stopped"], {"group": "信任與風險", "draws": 2, "results": {"材料無依據": 9, "無矛盾": 1}})
        self.assertEqual(self.fw("next", "topic", "--wait", "0").returncode, 3)
        self.ok("choose", "topic", "explore")
        self.assertIsNone(self.state()["stopped"])

    def test_long_materials_are_tagged_first_and_prompts_carry_only_what_their_pairs_touch(self):
        self.prepare()
        self.ok("start", "topic", "--seed", "7", "--fan", "1", "--index-over", "10")
        self.ok("choose", "topic", "begin")
        self.assertIn("材料還在整理", self.fw("choose", "topic", "explore").stderr)
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T001 index")
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        for wanted in ("某虛構城市在 2031 年推行的虛構登記制度", "1. 行動者的負擔（例如：", "39. ",
                       "[M01-P001] 第一段", "〈小標〉\n\n[M01-P003] 第三段", "最多標 4 個"):
            self.assertIn(wanted, prompt)
        for leaked in ("TRIZ", "移動物體", "規模與範圍", "只有主人知道", "{{"):
            self.assertNotIn(leaked, prompt)

        def tags(p1=(1, 2), **more):
            return {"rows": [{"p": "M01-P001", "dims": list(p1)}, {"p": "M01-P002", "dims": [3]},
                             {"p": "M01-P003", "dims": []}][:more.get("keep", 3)]}

        for data, message in ((tags(keep=2), "no row for M01-P003"), (tags(p1=(1, 40)), "dims must list at most 4"),
                              (tags(p1=(1, 2, 3, 4, 5)), "dims must list at most 4")):
            self.assertIn(message, self.answer(data, task).stderr)
        self.ok("choose", "topic", "cancel")
        self.assertIn("材料還在整理", self.fw("choose", "topic", "explore").stderr)
        self.ok("choose", "topic", "index")
        task, stop = self.tasks()
        self.assertEqual((stop, task["task"]), ({"stop": "T001"}, "T002 index"))
        r = self.answer(tags(), task)
        self.assertIn("materials tagged: 3 of 39 dimensions have passages; 738 pair(s) set aside", r.stdout)
        self.assertIn("0/741 pairs read", r.stdout)
        state = self.state()
        self.assertEqual((state["index"], state["tags"]["M01-P001"], len(state["visited"])), ("done", [1, 2], 738))

        self.ok("choose", "topic", "explore")
        (task,) = self.tasks()
        self.assertEqual(sorted(te.pair_id(a, b) for a, b in self.state()["tasks"][2]["items"]),
                         ["01x02", "01x03", "02x03"])
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        self.assertIn("[M01-P002] 第二段", prompt)
        self.assertNotIn("M01-P003", prompt)
        r = self.answer(rows(3, n1={"n": 1, "topics": [topic()]}), task)
        self.assertIn("3/741 pairs read, 1 topic(s)", r.stdout)
        self.assertIn("都看過或正在看了", self.fw("choose", "topic", "explore").stderr)
        self.ok("choose", "topic", "split", "Q001")
        prompt = (self.root / self.tasks()[0]["prompt"]).read_text(encoding="utf-8")
        self.assertIn("[M01-P001] 第一段", prompt)
        self.assertNotIn("[M01-P003]", prompt)

    def test_saving_the_anchor_has_the_examples_rewritten_for_the_field(self):
        self.prepare()
        self.ok("start", "topic", "--seed", "7", "--fan", "1")
        self.ok("choose", "topic", "anchor")
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T001 localize")
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        self.assertIn("某虛構城市在 2031 年推行的虛構登記制度", prompt)
        self.assertIn("39. ", prompt)
        self.assertNotIn("只有主人知道", prompt)
        self.assertIn("上一個工作還在進行", self.fw("choose", "topic", "begin").stderr)
        full = {"rows": [{"n": n, "examples": f"虛構例子{n}"} for n in range(1, 40)]}
        self.assertIn("needs one row for each of the 39", self.answer({"rows": full["rows"][:38]}, task).stderr)
        self.assertIn("longer than 80", self.answer(
            {"rows": full["rows"][:38] + [{"n": 39, "examples": "長" * 81}]}, task).stderr)
        self.assertEqual(self.answer(full, task).returncode, 0)
        self.ok("choose", "topic", "anchor")
        self.assertEqual(len(self.state()["tasks"]), 1)
        self.ok("choose", "topic", "begin")
        self.ok("choose", "topic", "explore")
        prompt = (self.root / self.tasks()[0]["prompt"]).read_text(encoding="utf-8")
        a, b = self.state()["tasks"][1]["items"][0]
        self.assertIn(f"（例如：虛構例子{a}）", prompt)
        self.assertNotIn(te.load_params()["by_n"][b]["examples"], prompt)


class PageTests(RunCase):
    def serve(self):
        os.environ["FW_COURSE_ROOT"] = str(self.root)
        self.addCleanup(os.environ.pop, "FW_COURSE_ROOT", None)
        server = te.make_server(te.topic_enum_paths(self.unit), 0)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{server.server_address[1]}"

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=10) as r:
            return r.read().decode("utf-8")

    def post(self, choice, header=True):
        req = urllib.request.Request(self.url + "/choose", data=json.dumps(choice).encode("utf-8"),
                                     headers={"X-Topic-Enumerate": "1"} if header else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_page_shows_the_ledger_and_buttons_write_to_it(self):
        self.found_topic()
        self.serve()
        self.assertIn("<title>選題</title>", self.get("/"))
        view = json.loads(self.get("/state"))
        self.assertEqual((view["read"], view["total"], view["out"], view["listening"]), (5, 741, 0, True))
        os.utime(self.run_dir / ".listening", (0, 0))
        self.assertFalse(json.loads(self.get("/state"))["listening"])
        self.assertEqual([g["name"] for g in view["groups"]],
                         ["規模與範圍", "權力、秩序與變遷", "資源與成本", "信任與風險", "治理與制度設計"])
        shown = view["topics"][0]
        self.assertEqual((view["stage"], shown["cited"][0]["file"]), ("explore", "虛構日報的報導"))
        self.assertEqual(shown["cited"][0]["text"], "第一段：登記變嚴格之後，申請人等待的時間變長。")
        self.assertEqual((shown["kept"], shown["can_vary"], shown["can_split"]), (False, True, True))

        self.assertEqual(self.post({"action": "keep", "topic": "Q001"}), (200, {"ok": True}))
        self.assertEqual(self.post({"action": "explore", "group": "規模與範圍"})[0], 200)
        self.assertEqual(self.post({"action": "vary", "topic": "Q001"})[0], 200)
        view = json.loads(self.get("/state"))
        self.assertEqual((view["drawer"], view["out"], view["waiting"], view["topics"][0]["can_vary"]),
                         (["Q001"], 2, 2, False))
        status, body = self.post({"action": "split", "topic": "Q404"})
        self.assertEqual((status, body["error"]), (409, "找不到這個題目"))
        self.assertEqual([t["task"] for t in self.tasks()], ["T002 explore", "T003 vary"])
        self.assertEqual(self.state()["tasks"][1]["group"], "規模與範圍")

    def test_setup_pages_take_the_anchor_then_the_materials_then_open_the_search(self):
        (self.root / "COURSE.md").write_text("# 課\n\n| | |\n| :--- | :--- |\n| Field | 虛構學門 |\n", encoding="utf-8")
        (self.base / "materials").mkdir(parents=True)
        (self.base / "materials" / "news.md").write_text(MATERIAL, encoding="utf-8")
        self.ok("start", "topic", "--seed", "7", "--fan", "1", "--stock-examples")
        self.serve()
        view = json.loads(self.get("/state"))
        self.assertEqual((view["stage"], view["anchor_fields"]["領域"], view["anchor_fields"]["現象"]),
                         ("anchor", "虛構學門", ""))
        self.assertNotIn("topics", view)
        self.assertEqual(self.post({"action": "explore"}), (409, {"error": "還沒開始選題"}))
        self.assertEqual(self.post({"action": "begin"})[1]["error"], "「現象」還沒填；「可得資料」還沒填；「指導與限制」還沒填")
        fields = {"領域": "虛構學門", "現象": " 某城市的登記制度 ", "可得資料": "", "指導與限制": ""}
        self.assertEqual(self.post({"action": "sharpen", "fields": dict(fields, 現象="")})[1]["error"], "「現象」還沒填")
        self.assertEqual(self.post({"action": "sharpen", "fields": fields})[0], 200)
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T001 sharpen")
        self.assertIn("某城市的登記制度", (self.root / task["prompt"]).read_text(encoding="utf-8"))
        self.assertIn("with 2 or 3 entries", self.answer({"options": [{"text": "只有一個", "why": "x"}]}, task).stderr)
        options = [{"text": "某城市 2031 年的〔哪一項〕登記", "why": "只看一項"}, {"text": "某城市的申請人", "why": "只看一方"}]
        self.assertEqual(self.answer({"options": options}, task).returncode, 0)
        view = json.loads(self.get("/state"))
        self.assertEqual((view["stage"], view["sharpen"], view["anchor_fields"]["現象"]),
                         ("anchor", options, "某城市的登記制度"))
        fields.update(可得資料="申請紀錄", 指導與限制="兩年")
        self.assertEqual(self.post({"action": "anchor", "fields": dict(fields, 現象=options[0]["text"])})[1]["error"],
                         "「現象」裡還有〔〕要補")
        self.assertEqual(self.post({"action": "anchor", "fields": fields})[0], 200)
        self.assertIn("## 現象\n\n某城市的登記制度\n", (self.base / "anchor.md").read_text(encoding="utf-8"))

        view = json.loads(self.get("/state"))
        only = view["materials"][0]
        self.assertEqual((view["stage"], only["id"], only["title"], only["source"], only["use"], only["origin"]),
                         ("materials", "M01", "虛構日報的報導", "虛構日報", True, "local"))
        self.assertEqual((view["sharpen"], len(view["dimensions"]), view["dimensions"][0]["passages"]), ([], 39, None))
        self.assertEqual(view["used_chars"], len(MATERIAL))
        self.assertEqual(self.post({"action": "use", "material": "M01", "on": False})[0], 200)
        self.assertIn("至少要勾選一份", self.post({"action": "begin"})[1]["error"])
        self.assertEqual(self.post({"action": "use", "material": "*", "on": True})[0], 200)
        self.assertEqual(json.loads(self.get("/state"))["materials"][0]["use"], True)
        self.assertEqual(self.post({"action": "collect"})[1]["error"], "還沒有搜尋範圍")

        self.assertEqual(self.post({"action": "scope"})[0], 200)
        self.assertEqual(self.post({"action": "begin"})[1]["error"], "上一個工作還在進行")
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T002 scope")
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        self.assertIn("某城市的登記制度", prompt)
        self.assertIn("- 虛構日報的報導", prompt)
        self.assertNotIn("申請紀錄", prompt)
        self.assertIn("起始日期要寫成 YYYY-MM-DD",
                      self.answer({"keywords": ["登記"], "from": "去年", "to": "2031-06-30"}, task).stderr)
        scope = {"keywords": ["登記制度", " registration "], "from": "2030-01-01", "to": "2031-06-30",
                 "sources": ["虛構日報", ""], "note": "偏重爭議"}
        self.assertEqual(self.answer(scope, task).returncode, 0)
        view = json.loads(self.get("/state"))
        self.assertEqual((view["scope"]["keywords"], view["scope"]["sources"], view["out"]),
                         (["登記制度", "registration"], ["虛構日報"], 0))

        edited = dict(view["scope"], keywords=["登記制度", "等待時間"])
        self.assertEqual(self.post({"action": "collect", "scope": edited})[0], 200)
        (task,) = self.tasks()
        self.assertEqual(task["task"], "T003 collect")
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        for wanted in ("  - 等待時間", "2030-01-01 到 2031-06-30", "  - 虛構日報",
                       f"`{self.base / 'materials'}/`", "- 虛構日報的報導"):
            self.assertIn(wanted, prompt)
        self.assertNotIn("registration", prompt)
        item = {"file": "2031-05-wait.md", "title": "t", "source": "s", "date": "2031-05-01", "url": "u"}
        r = self.answer({"items": [item, dict(item, file="../x.md")], "failed": [{"what": "某報"}]}, task)
        for message in ("item 1: 2031-05-wait.md is not in", "item 2: file must be the name", "failed 1: needs what and reason"):
            self.assertIn(message, r.stderr)
        (self.base / "materials" / "2031-05-wait.md").write_text(
            "---\ntitle: 等待變長的抱怨\nsource: 虛構晚報\ndate: 2031-05-01\nurl: https://example.invalid/a\n---\n\n第四段：申請人抱怨。\n",
            encoding="utf-8")
        r = self.answer({"items": [item], "failed": [{"what": "某報社論", "reason": "要付費"}]}, task)
        self.assertEqual(r.returncode, 0, r.stderr)
        view = json.loads(self.get("/state"))
        new = view["materials"][1]
        self.assertEqual((new["id"], new["title"], new["source"], new["date"], new["origin"], new["use"]),
                         ("M02", "等待變長的抱怨", "虛構晚報", "2031-05-01", "collected", True))
        self.assertEqual(view["failed"], [{"what": "某報社論", "reason": "要付費"}])

        self.assertEqual(self.post({"action": "use", "material": "M01", "on": False})[0], 200)
        self.assertEqual(self.post({"action": "begin"})[0], 200)
        view = json.loads(self.get("/state"))
        self.assertEqual((view["stage"], view["read"], view["topics"]), ("explore", 0, []))
        self.assertEqual(self.post({"action": "back"})[1]["error"][:6], "已經開始選題")
        self.assertEqual(self.post({"action": "explore"})[0], 200)
        (task,) = self.tasks()
        prompt = (self.root / task["prompt"]).read_text(encoding="utf-8")
        self.assertIn("[M02-P001] 第四段：申請人抱怨。", prompt)
        self.assertNotIn("M01-P", prompt)
        self.assertNotIn("https://example.invalid", prompt)

    def test_page_refuses_requests_a_foreign_site_could_send(self):
        self.start()
        self.serve()
        self.assertEqual(self.post({"action": "explore"}, header=False)[0], 403)
        self.assertEqual(self.state()["tasks"], [])
        req = urllib.request.Request(self.url + "/state", headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=10)
        with caught.exception as refused:
            self.assertEqual(refused.code, 403)


if __name__ == "__main__":
    unittest.main()
