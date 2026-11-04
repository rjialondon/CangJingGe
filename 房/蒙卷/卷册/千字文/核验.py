#!/usr/bin/env python3
"""千字文阶段一：只读核验关联索引，按唯一精确锚原位递文。Python 3.10+。"""
import sys

sys.dont_write_bytecode = True

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


内部经名 = frozenset(("周易本义-道观正本.md", "周易本义·道观正本.md"))


class 核验问题(ValueError):
    pass


def 须(条件, 说明):
    if not 条件:
        raise 核验问题(说明)


def 文本(值, 位置):
    须(type(值) is str and bool(值.strip()), f"{位置}须为非空文本")


def 对象(值, 字段, 位置):
    须(type(值) is dict, f"{位置}须为对象")
    须(set(值) == set(字段.split()), f"{位置}字段不符：应为 {字段}")


def 无重键(键值对):
    结果 = {}
    for 键, 值 in 键值对:
        须(键 not in 结果, f"JSON重复键：{键}")
        结果[键] = 值
    return 结果


def 寻阁根(源件):
    """只认项目固定相对层级；阁目录可改名或整体回迁，不依赖AGENTS。"""
    本件 = Path(源件).resolve()
    项目相对 = Path("房/蒙卷/卷册/千字文")
    须(本件.parent.parts[-len(项目相对.parts):] == 项目相对.parts,
       "源件须位于阁根下房/蒙卷/卷册/千字文，不向父链猜测馆藏根")
    return 本件.parents[len(项目相对.parts)]


def 馆藏路径(阁根, 相对):
    文本(相对, "馆藏路径")
    路 = Path(相对)
    须(not 路.is_absolute() and ".." not in 路.parts, f"拒绝绝对或上溯路径：{相对}")
    try:
        阁根 = Path(阁根).resolve()
        真路 = (阁根 / 路).resolve()
    except (OSError, RuntimeError) as 问题:
        raise 核验问题(f"馆藏路径无法解析：{相对}：{问题}") from 问题
    须(真路.is_relative_to(阁根), f"路径或软链越出馆藏：{相对}")
    须(路.name not in 内部经名 and 真路.name not in 内部经名,
       f"道观内部经不可绑定为外部原书：{相对}")
    须(真路.is_file(), f"馆藏不存在或不是文件：{相对}")
    return 真路


def 读源(阁根, 相对):
    字节 = 馆藏路径(阁根, 相对).read_bytes()
    return 字节.decode("utf-8"), hashlib.sha256(字节).hexdigest()


def 唯一锚(全文, 锚, 起, 止, 位置):
    文本(锚, 位置)
    首 = 全文.find(锚, 起, 止)
    须(首 >= 0, f"{位置}缺失：{锚!r}")
    须(全文.find(锚, 首 + 1, 止) < 0, f"{位置}重现，须增加范围限定：{锚!r}")
    return 首


def 限定范围(全文, 范围, 位置, 包含止锚=False):
    """逐层唯一限定；书篇不含止锚，千字文正文单层包含末锚。"""
    层列 = 范围 if type(范围) is list else [范围]
    须(bool(层列), f"{位置}范围不得为空")
    起, 止 = 0, len(全文)
    for 层号, 层 in enumerate(层列, 1):
        名 = f"{位置}第{层号}层"
        对象(层, "起锚 止锚", 名)
        新起 = 唯一锚(全文, 层["起锚"], 起, 止, 名 + "起锚")
        新止 = 唯一锚(全文, 层["止锚"], 起, 止, 名 + "止锚")
        须(新起 + len(层["起锚"]) <= 新止, f"{名}起止锚逆序或重叠")
        起, 止 = 新起, 新止 + (len(层["止锚"]) if 包含止锚 else 0)
    return 起, 止


def 所在段(全文, 起, 止, 锚起, 锚止, 位置):
    段起 = 起
    for 间隔 in re.finditer(r"\r?\n[^\S\r\n]*\r?\n(?:[^\S\r\n]*\r?\n)*", 全文[起:止]):
        段止 = 起 + 间隔.start()
        if 段起 <= 锚起 and 锚止 <= 段止:
            return 段起, 段止
        段起 = 起 + 间隔.end()
    须(段起 <= 锚起 and 锚止 <= 止, f"{位置}定位摘句跨空行分段")
    return 段起, 止


def 核验(索引, 阁根):
    对象(索引, "格式 路径基准 正文 书目 落点 入口", "索引")
    须(type(索引["格式"]) is int and 索引["格式"] == 1, "仅支持格式1")
    须(索引["路径基准"] == "藏经阁根目录", "路径基准须为藏经阁根目录")
    正文 = 索引["正文"]
    对象(正文, "路径 起锚 止锚 字数 每句字数", "正文")
    须(type(正文["字数"]) is int and 正文["字数"] == 1000, "正文字数须为1000")
    须(type(正文["每句字数"]) is int and 正文["每句字数"] == 4, "每句字数须为4")
    全文, 正文指纹 = 读源(阁根, 正文["路径"])
    起, 止 = 限定范围(全文, {键: 正文[键] for 键 in ("起锚", "止锚")}, "正文", True)
    句文 = "".join(全文[起:止].split())
    须(len(句文) == 正文["字数"] and len(句文) % 4 == 0,
       f"正文字数不符：实得{len(句文)}，应为1000且可整分四字句")
    书目, 落点, 入口列 = 索引["书目"], 索引["落点"], 索引["入口"]
    须(type(书目) is dict and bool(书目), "书目须为非空对象")
    须(type(落点) is dict and bool(落点), "落点须为非空对象")
    须(type(入口列) is list and bool(入口列), "入口须为非空数组")
    书源, 取文表, 标识集 = {}, {}, set()
    for 书号, 书 in 书目.items():
        文本(书号, "书目标识")
        对象(书, "书名 路径 内容时代 版本说明", "书目·" + 书号)
        for 键, 值 in 书.items():
            文本(值, f"书目·{书号}·{键}")
        书源[书号] = 读源(阁根, 书["路径"])
    for 点号, 点 in 落点.items():
        文本(点号, "落点标识")
        名 = "落点·" + 点号
        对象(点, "书目 篇名 状态 范围 定位摘句 取文 经注说明", 名)
        for 键 in ("书目", "篇名", "状态", "定位摘句", "取文", "经注说明"):
            文本(点[键], 名 + "·" + 键)
        须(点["状态"] == "已接通", 名 + "仅支持已接通落点")
        须(点["取文"] in ("所在段", "本篇"), 名 + "取文只可为所在段或本篇")
        须(点["书目"] in 书源, 名 + "引用未知书目")
        源文, 指纹 = 书源[点["书目"]]
        起, 止 = 限定范围(源文, 点["范围"], 名)
        锚起 = 唯一锚(源文, 点["定位摘句"], 起, 止, 名 + "定位摘句")
        if 点["取文"] == "所在段":
            起, 止 = 所在段(源文, 起, 止, 锚起, 锚起 + len(点["定位摘句"]), 名)
        取文表[点号] = {"原文": 源文[起:止], "源SHA256": 指纹,
                       "片段SHA256": hashlib.sha256(源文[起:止].encode("utf-8")).hexdigest(),
                       "起行": 源文.count("\n", 0, 起) + 1,
                       "止行": 源文.count("\n", 0, max(起, 止 - 1)) + 1}
    for 入口 in 入口列:
        对象(入口, "标识 句段 导读 学科 关联", "入口")
        for 键 in ("标识", "导读"):
            文本(入口[键], "入口·" + 键)
        名 = "入口·" + 入口["标识"]
        须(入口["标识"] not in 标识集, 名 + "标识重复")
        标识集.add(入口["标识"])
        句段 = 入口["句段"]
        对象(句段, "起句 止句 原文", 名 + "句段")
        起句, 止句 = 句段["起句"], 句段["止句"]
        须(type(起句) is int and type(止句) is int and 1 <= 起句 <= 止句 <= len(句文) // 4,
           名 + "句序须为正文内从1起的连续闭区间")
        须(type(句段["原文"]) is str and 句段["原文"] == 句文[(起句 - 1) * 4:止句 * 4],
           名 + "原句与正文切片不符")
        for 键 in ("学科", "关联"):
            列 = 入口[键]
            须(type(列) is list and bool(列), 名 + 键 + "须为非空数组")
            for 值 in 列:
                文本(值, 名 + 键)
            须(len(set(列)) == len(列), 名 + 键 + "不得重复")
        for 点号 in 入口["关联"]:
            须(点号 in 落点, 名 + "引用未知关联：" + 点号)
    return 取文表, 正文指纹


def 展示(索引, 取文表, 标识):
    入口 = next((项 for 项 in 索引["入口"] if 项["标识"] == 标识), None)
    须(入口 is not None, "未登记入口：" + 标识)
    print(f"入口：{标识}｜{入口['句段']['原文']}")
    print("后作导读：" + 入口["导读"])
    for 点号 in 入口["关联"]:
        点, 取文 = 索引["落点"][点号], 取文表[点号]
        书 = 索引["书目"][点["书目"]]
        print(f"\n《{书['书名']}》·{点['篇名']}｜{点['取文']}")
        print(f"内容时代：{书['内容时代']}\n版本说明：{书['版本说明']}")
        print(f"经注说明：{点['经注说明']}")
        print(f"源：{书['路径']}:{取文['起行']}-{取文['止行']}")
        print(f"源文件SHA256：{取文['源SHA256']}\n片段SHA256：{取文['片段SHA256']}")
        print("——馆藏原位切片开始——")
        sys.stdout.write(取文["原文"])
        if not 取文["原文"].endswith("\n"):
            print()
        print("——馆藏原位切片结束（边框换行不属原文）——")


def 自检():
    """只造微型源文与一份索引；所有夹具、搬迁副本均只入临时目录。"""
    已验 = []
    with tempfile.TemporaryDirectory(prefix="千字文核验-") as 临时名:
        临时 = Path(临时名).resolve()
        阁根 = 临时 / "带空格 任意改名的阁"
        项目 = 阁根 / "房/蒙卷/卷册/千字文"
        项目.mkdir(parents=True)
        正文 = "𠀀天地玄" + "甲" * 992 + "宇宙洪荒"
        甲书 = "# 外一\n\n## 本篇\n\n　甲书原字𠀀。  \n下一行。\n\n## 次篇\n\n余文\n# 外二\n\n## 本篇\n\n重名篇。\n\n## 次篇\n"
        乙书 = "# 乙篇\n\n乙书原字。\n\n# 乙后\n"
        for 名, 内容 in (("正文.md", 正文), ("甲.md", 甲书), ("乙.md", 乙书)):
            (阁根 / 名).write_bytes(内容.encode("utf-8"))
        索引 = {"格式": 1, "路径基准": "藏经阁根目录",
                "正文": {"路径": "正文.md", "起锚": "𠀀天地玄", "止锚": "宇宙洪荒", "字数": 1000, "每句字数": 4},
                "书目": {号: {"书名": 号, "路径": f"{号}.md", "内容时代": "夹具", "版本说明": "仅为自检"} for 号 in ("甲", "乙")},
                "落点": {"甲段": {"书目": "甲", "篇名": "本篇", "状态": "已接通", "范围": [{"起锚": "# 外一", "止锚": "# 外二"}, {"起锚": "## 本篇", "止锚": "## 次篇"}], "定位摘句": "甲书原字𠀀。", "取文": "所在段", "经注说明": "夹具"},
                         "乙篇": {"书目": "乙", "篇名": "乙篇", "状态": "已接通", "范围": {"起锚": "# 乙篇", "止锚": "# 乙后"}, "定位摘句": "乙书原字。", "取文": "本篇", "经注说明": "夹具"}},
                "入口": [{"标识": f"{数}字", "句段": {"起句": 1, "止句": 数 // 4, "原文": 正文[:数]}, "导读": "夹具", "学科": ["蒙学"], "关联": ["甲段", "乙篇"] if 数 == 4 else ["甲段"]} for 数 in (4, 8, 16)]}
        索引["入口"].append({"标识": "末句", "句段": {"起句": 250, "止句": 250, "原文": "宇宙洪荒"}, "导读": "夹具", "学科": ["蒙学"], "关联": ["乙篇"]})
        前像 = {路.relative_to(阁根): 路.read_bytes() for 路 in 阁根.glob("*.md")}
        取文表, _ = 核验(索引, 阁根)
        须(取文表["甲段"]["原文"] == "　甲书原字𠀀。  \n下一行。", "原文切片发生转换")
        须((取文表["甲段"]["起行"], 取文表["甲段"]["止行"]) == (5, 6), "源行号偏移")
        已验 += ["4/8/16字及末句", "多书与同书复用", "扩展汉字", "嵌套同名章节", "原字空白与源行"]

        def 病例(名, 改动, 预期):
            病本 = copy.deepcopy(索引)
            改动(病本)
            try:
                核验(病本, 阁根)
            except 核验问题 as 问题:
                须(预期 in str(问题), f"{名}拒因不符：{问题}")
                已验.append(名)
                return
            raise 核验问题(名 + "未被拒绝")

        病例("锚重现", lambda 本: 本["落点"]["甲段"].update(范围={"起锚": "## 本篇", "止锚": "## 次篇"}), "重现")
        病例("锚缺失", lambda 本: 本["落点"]["乙篇"].update(定位摘句="缺失原句"), "缺失")
        病例("锚逆序", lambda 本: 本["落点"]["乙篇"].update(范围={"起锚": "# 乙后", "止锚": "# 乙篇"}), "逆序")
        病例("跨段摘句", lambda 本: 本["落点"]["乙篇"].update(取文="所在段", 定位摘句="# 乙篇\n\n乙书原字。"), "跨空行")
        病例("未知关联", lambda 本: 本["入口"][0].update(关联=["未登记"]), "未知关联")
        病例("原句错误", lambda 本: 本["入口"][0]["句段"].update(原文="错误原句"), "不符")
        for 起句, 止句 in ((0, 1), (2, 1), (1, 251), (True, 1)):
            病例(f"非法句序{起句}/{止句}", lambda 本: 本["入口"][0]["句段"].update(起句=起句, 止句=止句), "句序")
        for 路名 in ("../逃逸.md", "房/../../逃逸.md", str(临时 / "绝对.md"), ".", "缺失.md", "藏经阁/正文.md"):
            病例("拒路径" + 路名, lambda 本: 本["正文"].update(路径=路名),
               "不是文件" if 路名 in (".", "缺失.md", "藏经阁/正文.md") else "路径")
        外件 = 临时 / "外件.md"
        外件.write_text("不许读", encoding="utf-8")
        (阁根 / "软链.md").symlink_to(外件)
        病例("软链越界", lambda 本: 本["正文"].update(路径="软链.md"), "越出")
        (阁根 / "外目录").symlink_to(临时, target_is_directory=True)
        病例("目录软链越界", lambda 本: 本["正文"].update(路径="外目录/外件.md"), "越出")
        (阁根 / "馆内链.md").symlink_to("甲.md")
        须(读源(阁根, "馆内链.md") == 读源(阁根, "甲.md"), "馆内软链应仍归阁根")
        for 序, 内部名 in enumerate(sorted(内部经名)):
            (阁根 / 内部名).write_bytes(甲书.encode("utf-8"))
            别名 = f"内部别名{序}.md"
            (阁根 / 别名).symlink_to(内部名)
            for 路名 in (内部名, 别名):
                病例("拒内部经" + 路名, lambda 本: 本["书目"]["甲"].update(路径=路名), "道观内部经")
        (阁根 / "周易本义.md").write_bytes(甲书.encode("utf-8"))
        外本 = copy.deepcopy(索引)
        外本["书目"]["甲"]["路径"] = "周易本义.md"
        须(核验(外本, 阁根) == 核验(索引, 阁根), "外部原书周易本义.md不应被误拒")
        已验.append("外部原书周易本义不误伤")
        根链 = 临时 / "阁根别名"
        根链.symlink_to(阁根, target_is_directory=True)
        须(核验(索引, 根链) == 核验(索引, 阁根), "根本身须resolve后作信任根")
        须(寻阁根(根链 / "房/蒙卷/卷册/千字文/核验.py") == 阁根,
           "根别名的固定层级寻阁不符")
        已验 += ["馆内软链", "根软链resolve为信任根"]
        病例("旧路径基准不兼容", lambda 本: 本.update(路径基准="道观根目录"), "路径基准")
        病例("未知字段", lambda 本: 本.update(多余=True), "字段不符")
        try:
            json.loads('{"甲":1,"甲":2}', object_pairs_hook=无重键)
        except 核验问题:
            已验.append("JSON重复键")
        else:
            raise 核验问题("JSON重复键未拒绝")
        (项目 / "关联索引.json").write_text(json.dumps(索引, ensure_ascii=False), encoding="utf-8")
        副本 = 项目 / "核验.py"
        副本.write_bytes(Path(__file__).read_bytes())
        for 路名 in (*sorted(内部经名), "内部别名0.md", "内部别名1.md", "周易本义.md"):
            本 = copy.deepcopy(索引)
            本["书目"]["甲"]["路径"] = 路名
            (项目 / "关联索引.json").write_text(json.dumps(本, ensure_ascii=False), encoding="utf-8")
            运行 = subprocess.run([sys.executable, "-B", str(副本)], cwd=临时,
                                  capture_output=True, text=True, timeout=15)
            if 路名 == "周易本义.md":
                须(运行.returncode == 0, "命令行误拒外部原书：" + 运行.stderr)
            else:
                须(运行.returncode == 1 and "道观内部经" in 运行.stderr,
                   "命令行未明确拒绝内部经：" + 路名)
        (项目 / "关联索引.json").write_text(json.dumps(索引, ensure_ascii=False), encoding="utf-8")
        已验 += ["命令行拒内部经及馆内别名", "命令行外部原书不误伤"]
        for 错位 in (临时 / "核验.py", 临时 / "藏经阁/蒙卷/千字文/核验.py",
                      临时 / "房/蒙卷/卷册/其他项目/核验.py"):
            try:
                寻阁根(错位)
            except 核验问题:
                pass
            else:
                raise 核验问题("错位源件不应误找桌面或父目录")
        for 回迁 in (False, True):
            if 回迁:
                新阁根 = 临时 / "回迁道观/藏经阁"
                新阁根.parent.mkdir()
                阁根.rename(新阁根)
                阁根 = 新阁根
                副本 = 阁根 / "房/蒙卷/卷册/千字文/核验.py"
            须(寻阁根(副本) == 阁根, "独立改名或回迁的阁根识别错误")
            须(not (阁根.parent / "AGENTS.md").exists(), "夹具不应依赖AGENTS")
            for 参数 in ([], ["--展示", "4字"], ["--展示", "未登记"]):
                运行 = subprocess.run([sys.executable, "-B", str(副本), *参数], cwd=临时,
                                      capture_output=True, text=True, timeout=15)
                须(运行.returncode == (1 if "未登记" in 参数 else 0), "异cwd命令行结果不符：" + 运行.stderr)
                if "4字" in 参数:
                    须(取文表["甲段"]["原文"] in 运行.stdout, "命令行未输出原位切片")
            须(all((阁根 / 路).read_bytes() == 内容 for 路, 内容 in 前像.items()), "源文件被改动")
            须(not list(阁根.rglob("__pycache__")), "自检留下字节缓存")
        已验 += ["错位不猜父目录", "独立改名无AGENTS异cwd运行", "回迁道观无AGENTS异cwd运行",
                 "未知入口非零退出", "源文件未改", "无字节缓存"]
    print(f"自检通过：{len(已验)}项；临时夹具已清理。")
    for 项 in 已验:
        print("  ✓ " + 项)


def 主程():
    命令 = argparse.ArgumentParser(description=__doc__)
    选项 = 命令.add_mutually_exclusive_group()
    选项.add_argument("--展示", metavar="入口标识")
    选项.add_argument("--自检", action="store_true")
    参数 = 命令.parse_args()
    try:
        if 参数.自检:
            自检()
            return 0
        本件 = Path(__file__).resolve()
        阁根 = 寻阁根(本件)
        索引 = json.loads((本件.parent / "关联索引.json").read_bytes().decode("utf-8"), object_pairs_hook=无重键)
        取文表, 指纹 = 核验(索引, 阁根)
        if 参数.展示 is not None:
            展示(索引, 取文表, 参数.展示)
        else:
            print(f"核验通过：正文1000字／250句；{len(索引['入口'])}入口、{len(索引['书目'])}书目、{len(取文表)}落点。")
            print("正文源文件SHA256：" + 指纹)
        return 0
    except (核验问题, OSError, UnicodeError, json.JSONDecodeError, subprocess.SubprocessError) as 问题:
        print("核验失败：" + str(问题), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(主程())
