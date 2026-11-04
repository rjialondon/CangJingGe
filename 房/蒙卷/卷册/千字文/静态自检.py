#!/usr/bin/env python3
"""只在系统tmp造微夹具，核对静态产物与现役只读接口；不复制真实馆藏。"""
import sys

sys.dont_write_bytecode = True

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


本目录 = Path(__file__).resolve().parent
模块说明 = importlib.util.spec_from_file_location("千字文静态自检构建", 本目录 / "静态构建.py")
构 = importlib.util.module_from_spec(模块说明)
模块说明.loader.exec_module(构)


class 静态检查(unittest.TestCase):
    def setUp(self):
        self.临时 = tempfile.TemporaryDirectory(prefix="千字文静态自检-")
        self.addCleanup(self.临时.cleanup)
        self.临根 = Path(self.临时.name).resolve()
        self.阁根 = self.临根 / "改名 独立阁"
        self.项目 = self.阁根 / "房/蒙卷/卷册/千字文"
        self.页面 = self.项目 / "页面"
        self.页面.mkdir(parents=True)
        self.句文 = "𠀀天地玄" + "甲" * 992 + "宇宙洪荒"
        self.正文 = "# 夹具\r\n\r\n" + "　".join(self.句文[起:起 + 4] for 起 in range(0, 1000, 4)) + "\r\n"
        self.甲文 = ("# 外一\r\n\r\n## 本篇\r\n\r\n　甲书原字𠀀。  \r\n第二行。\r\n\r\n"
                     + "长行𠀀" * 4200 + "<script>仅为原文</script>\r\n\r\n## 次篇\r\n余文\r\n"
                     + "# 外二\r\n## 本篇\r\n重名篇\r\n## 次篇\r\n")
        self.乙文 = "# 乙篇\n\n乙书原字。\n\n# 乙后\n尾页。\n"
        self.源 = {"正文.md": self.正文, "甲.md": self.甲文, "乙.md": self.乙文}
        for 名, 文 in self.源.items():
            (self.阁根 / 名).write_bytes(文.encode("utf-8"))
        self.页面文 = {
            "index.html": b'<!doctype html>\r\n<meta name="qzw-data-mode" content="live">\r\n',
            "app.js": b"'use strict';\n", "style.css": b"body { color: black; }\n",
            # 仅验二进制原样递送，不将微夹具冒充可渲染字体。
            "fonts/qzw-rare-214dc.woff2": b"wOF2\x00\xff\x80\r\nfixture-214dc",
            "fonts/OFL.txt": b"SIL OPEN FONT LICENSE Version 1.1\nfixture only\n"}
        for 名, 字节 in self.页面文.items():
            (self.页面 / 名).parent.mkdir(parents=True, exist_ok=True)
            (self.页面 / 名).write_bytes(字节)
        (self.阁根 / "未登记私纸.md").write_text("禁止公开的私纸哨兵", encoding="utf-8")
        (self.项目 / "开发纸.md").write_text("禁止公开的开发纸哨兵", encoding="utf-8")
        (self.项目 / "不应公开.py").write_text("禁止公开的代码哨兵", encoding="utf-8")
        (self.页面 / "额外资源.txt").write_text("禁止公开的页面哨兵", encoding="utf-8")
        (self.页面 / "fonts/未登记字体.woff2").write_text("禁止公开的字体哨兵", encoding="utf-8")
        self.索引 = {"格式": 1, "路径基准": "藏经阁根目录",
            "正文": {"路径": "正文.md", "起锚": "𠀀天地玄", "止锚": "宇宙洪荒", "字数": 1000, "每句字数": 4},
            "书目": {号: {"书名": 号, "路径": f"{号}.md", "内容时代": "夹具", "版本说明": "仅为测试"} for 号 in ("甲", "乙")},
            "落点": {
                "甲段": {"书目": "甲", "篇名": "本篇", "状态": "已接通", "范围": [{"起锚": "# 外一", "止锚": "# 外二"}, {"起锚": "## 本篇", "止锚": "## 次篇"}], "定位摘句": "甲书原字𠀀。", "取文": "所在段", "经注说明": "原样"},
                "乙篇": {"书目": "乙", "篇名": "乙篇", "状态": "已接通", "范围": {"起锚": "# 乙篇", "止锚": "# 乙后"}, "定位摘句": "乙书原字。", "取文": "本篇", "经注说明": "原样"}},
            "入口": [{"标识": "qzw-4", "句段": {"起句": 1, "止句": 1, "原文": self.句文[:4]}, "导读": "夹具", "学科": ["蒙学"], "关联": ["甲段", "乙篇"]},
                     {"标识": "qzw-8", "句段": {"起句": 1, "止句": 2, "原文": self.句文[:8]}, "导读": "夹具", "学科": ["蒙学"], "关联": ["甲段"]}]}
        self.写索引()
        self.输出序 = 0

    def 写索引(self, 本=None):
        (self.项目 / "关联索引.json").write_text(json.dumps(self.索引 if 本 is None else 本, ensure_ascii=False), encoding="utf-8")

    def 新输出(self):
        self.输出序 += 1
        路 = self.临根 / f"产物-{self.输出序}"
        路.mkdir()
        return 路

    def 读JSON(self, 根, 相对):
        return json.loads((根 / 相对).read_bytes())

    def 前像(self):
        return {路.relative_to(self.阁根): 路.read_bytes() for 路 in self.阁根.rglob("*") if 路.is_file()}

    def test_全清单与现役接口同形逐字拼回(self):
        前像 = self.前像()
        输出 = self.新输出()
        清单 = 构.构建(self.项目, 输出)
        self.assertEqual(self.读JSON(输出, "manifest.json"), 清单)
        self.assertEqual(set(清单), {"格式", "目录", "入口", "续读"})
        self.assertEqual(清单["格式"], 1)
        self.assertEqual(清单["目录"], "data/catalog.json")
        self.assertEqual(set(清单["入口"]), {"qzw-4", "qzw-8"})
        self.assertEqual(set(清单["续读"]), {"甲段", "乙篇"})
        self.assertEqual(self.读JSON(输出, 清单["目录"]), 构.预览.取接口(self.项目, self.阁根, "/api/catalog", {}))
        登记路径 = {"index.html", "app.js", "style.css", "fonts/qzw-rare-214dc.woff2",
                    "fonts/OFL.txt", ".nojekyll", "manifest.json", 清单["目录"]}
        for 入口, 路 in 清单["入口"].items():
            self.assertRegex(路, r"^data/entry/[0-9a-f]{64}\.json$")
            登记路径.add(路)
            self.assertEqual(self.读JSON(输出, 路), 构.预览.取接口(self.项目, self.阁根, "/api/entry", {"id": 入口}))
        for 点号, 模式表 in 清单["续读"].items():
            self.assertEqual(set(模式表), {"context", "chapter", "book"})
            文 = self.源[self.索引["书目"][self.索引["落点"][点号]["书目"]]["路径"]]
            篇起, 篇止, 段起, 段止 = 构.预览.定位(self.索引, 点号, 文)
            范围表 = {"context": (max(篇起, 段起 - 800), min(篇止, 段止 + 800)),
                      "chapter": (篇起, 篇止), "book": (0, len(文))}
            for 模式, 页表 in 模式表.items():
                合文, 偏移, 遍历 = "", 0, set()
                while 偏移 is not None:
                    路 = 页表[str(偏移)]
                    self.assertRegex(路, r"^data/read/[0-9a-f]{64}\.json$")
                    登记路径.add(路)
                    页 = self.读JSON(输出, 路)
                    现役 = 构.预览.取接口(self.项目, self.阁根, "/api/read", {"id": 点号, "mode": 模式, "offset": str(偏移)})
                    self.assertEqual(页, 现役)
                    self.assertEqual(页["源SHA256"], 构.预览.指纹(文))
                    self.assertEqual(页["片段SHA256"], 构.预览.指纹(页["原文"]))
                    self.assertLessEqual(len(页["原文"]), 6000)
                    self.assertEqual(页["前页"], max(0, 偏移 - 6000) if 偏移 else None)
                    遍历.add(str(偏移))
                    合文 += 页["原文"]
                    偏移 = 页["后页"]
                self.assertEqual(遍历, set(页表))
                self.assertEqual(合文, 文[slice(*范围表[模式])])
        self.assertGreaterEqual(len(清单["续读"]["甲段"]["book"]), 3)
        self.assertEqual(self.前像(), 前像)
        实有 = {路.relative_to(输出).as_posix() for 路 in 输出.rglob("*") if 路.is_file()}
        self.assertEqual(实有, 登记路径)
        for 路 in 输出.rglob("*"):
            if 路.is_file():
                字节 = 路.read_bytes()
                self.assertNotIn("禁止公开".encode("utf-8"), 字节)
                self.assertNotIn(str(self.临根).encode("utf-8"), 字节)
        self.assertEqual((输出 / "index.html").read_bytes(), self.页面文["index.html"].replace(b'content="live"', b'content="static"'))
        for 名 in ("app.js", "style.css", "fonts/qzw-rare-214dc.woff2", "fonts/OFL.txt"):
            self.assertEqual((输出 / 名).read_bytes(), self.页面文[名])
        self.assertFalse((输出 / "fonts/未登记字体.woff2").exists())
        self.assertFalse(list(self.阁根.rglob("__pycache__")))

    def test_每本书只预载一次(self):
        原读, 读过 = 构.预览.核.读源, []
        def 记读(根, 路):
            读过.append(路)
            return 原读(根, 路)
        构.预览.核.读源 = 记读
        try:
            构.构建(self.项目, self.新输出())
        finally:
            构.预览.核.读源 = 原读
        self.assertCountEqual(读过, ["正文.md", "甲.md", "乙.md"])

    def test_纯分页不读写及原索引不变(self):
        前本 = copy.deepcopy(self.索引)
        原读 = 构.预览.核.读源
        def 不许读(*参数):
            self.fail("纯取分页不应读文件")
        构.预览.核.读源 = 不许读
        try:
            页 = 构.预览.取分页(self.索引, "甲段", self.甲文, 构.预览.指纹(self.甲文), "book", 6000)
            self.assertEqual(页["原文"], self.甲文[6000:12000])
            self.assertEqual(self.索引, 前本)
        finally:
            构.预览.核.读源 = 原读

    def test_拒越界源及软链且输出仍空(self):
        外件 = self.临根 / "外件.md"
        外件.write_text(self.甲文, encoding="utf-8")
        (self.阁根 / "外链.md").symlink_to(外件)
        (self.阁根 / "外目录").symlink_to(self.临根, target_is_directory=True)
        for 路 in ("../外件.md", str(外件), "外链.md", "外目录/外件.md"):
            with self.subTest(路=路):
                本 = copy.deepcopy(self.索引)
                本["书目"]["甲"]["路径"] = 路
                self.写索引(本)
                输出 = self.新输出()
                with self.assertRaises(ValueError):
                    构.构建(self.项目, 输出)
                self.assertEqual(list(输出.iterdir()), [])

    def test_拒内部经及馆内别名且输出仍空(self):
        for 序, 内部名 in enumerate(("周易本义-道观正本.md", "周易本义·道观正本.md")):
            (self.阁根 / 内部名).write_bytes(self.甲文.encode("utf-8"))
            别名 = f"内部别名{序}.md"
            (self.阁根 / 别名).symlink_to(内部名)
            for 路 in (内部名, 别名):
                with self.subTest(路=路):
                    本 = copy.deepcopy(self.索引)
                    本["书目"]["甲"]["路径"] = 路
                    self.写索引(本)
                    输出 = self.新输出()
                    with self.assertRaisesRegex(构.预览.核.核验问题, "道观内部经"):
                        构.构建(self.项目, 输出)
                    self.assertEqual(list(输出.iterdir()), [])

    def test_外部原书周易本义仍可构建(self):
        (self.阁根 / "周易本义.md").write_bytes(self.甲文.encode("utf-8"))
        self.索引["书目"]["甲"]["路径"] = "周易本义.md"
        self.写索引()
        输出 = self.新输出()
        清单 = 构.构建(self.项目, 输出)
        页 = self.读JSON(输出, 清单["续读"]["甲段"]["book"]["0"])
        self.assertEqual(页["原文"], self.甲文[:6000])
        self.assertEqual(页["路径"], "周易本义.md")

    def test_拒危险非空相对输出且不触动原件(self):
        空 = self.新输出()
        非空 = self.新输出()
        (非空 / "旧产物").write_bytes(b"keep")
        内空 = self.阁根 / "不许产出"
        内空.mkdir()
        软链 = self.临根 / "输出别名"
        软链.symlink_to(空, target_is_directory=True)
        for 路 in (Path("/"), Path.home(), Path(tempfile.gettempdir()), self.阁根, self.项目,
                   内空, self.临根, 非空, 软链, "相对输出", self.临根 / "未创建", 空 / ".." / 空.name):
            with self.subTest(路=路), self.assertRaises(构.构建问题):
                构.构建(self.项目, 路)
        self.assertEqual((非空 / "旧产物").read_bytes(), b"keep")
        self.assertEqual(list(空.iterdir()), [])
        self.assertEqual(list(内空.iterdir()), [])

    def test_缺锚旧基准及重复键在落盘前拒绝(self):
        for 病型 in ("缺锚", "旧基准", "重复键"):
            with self.subTest(病型=病型):
                本 = copy.deepcopy(self.索引)
                if 病型 == "缺锚":
                    本["落点"]["甲段"]["定位摘句"] = "无此句"
                elif 病型 == "旧基准":
                    本["路径基准"] = "道观根目录"
                self.写索引(本)
                if 病型 == "重复键":
                    (self.项目 / "关联索引.json").write_text('{"格式":1,"格式":1}', encoding="utf-8")
                输出 = self.新输出()
                with self.assertRaises(ValueError):
                    构.构建(self.项目, 输出)
                self.assertEqual(list(输出.iterdir()), [])

    def test_拒页面与索引软链逃逸(self):
        外页 = self.临根 / "外页.html"
        外页.write_bytes(self.页面文["index.html"])
        (self.页面 / "index.html").unlink()
        (self.页面 / "index.html").symlink_to(外页)
        输出 = self.新输出()
        with self.assertRaises(ValueError):
            构.构建(self.项目, 输出)
        self.assertEqual(list(输出.iterdir()), [])
        (self.页面 / "index.html").unlink()
        (self.页面 / "index.html").write_bytes(self.页面文["index.html"])
        外索引 = self.临根 / "外索引.json"
        外索引.write_bytes((self.项目 / "关联索引.json").read_bytes())
        (self.项目 / "关联索引.json").unlink()
        (self.项目 / "关联索引.json").symlink_to(外索引)
        with self.assertRaises(ValueError):
            构.构建(self.项目, 输出)
        self.assertEqual(list(输出.iterdir()), [])

    def test_字体与许可证缺失在落盘前拒绝(self):
        for 名 in ("fonts/qzw-rare-214dc.woff2", "fonts/OFL.txt"):
            with self.subTest(名=名):
                源 = self.页面 / 名
                源.unlink()
                try:
                    输出 = self.新输出()
                    with self.assertRaises(ValueError):
                        构.构建(self.项目, 输出)
                    self.assertEqual(list(输出.iterdir()), [])
                finally:
                    源.write_bytes(self.页面文[名])

    def test_字体与许可证软链越界在落盘前拒绝(self):
        外件 = self.临根 / "外资源.bin"
        for 名 in ("fonts/qzw-rare-214dc.woff2", "fonts/OFL.txt"):
            with self.subTest(名=名):
                外件.write_bytes(self.页面文[名])
                源 = self.页面 / 名
                源.unlink()
                源.symlink_to(外件)
                try:
                    输出 = self.新输出()
                    with self.assertRaises(ValueError):
                        构.构建(self.项目, 输出)
                    self.assertEqual(list(输出.iterdir()), [])
                finally:
                    源.unlink()
                    源.write_bytes(self.页面文[名])

    def test_字体目录软链越界在落盘前拒绝(self):
        外目录 = self.临根 / "外字体目录"
        字体目录 = self.页面 / "fonts"
        字体目录.rename(外目录)
        字体目录.symlink_to(外目录, target_is_directory=True)
        输出 = self.新输出()
        with self.assertRaises(ValueError):
            构.构建(self.项目, 输出)
        self.assertEqual(list(输出.iterdir()), [])

    def test_页面模式必须唯一且构建可复现(self):
        for 字节 in (b"<html></html>", self.页面文["index.html"] * 2,
                     self.页面文["index.html"] + b'<meta name="qzw-data-mode" content="static">'):
            (self.页面 / "index.html").write_bytes(字节)
            输出 = self.新输出()
            with self.assertRaises(构.构建问题):
                构.构建(self.项目, 输出)
            self.assertEqual(list(输出.iterdir()), [])
        (self.页面 / "index.html").write_bytes(self.页面文["index.html"])
        甲, 乙 = self.新输出(), self.新输出()
        构.构建(self.项目, 甲)
        构.构建(self.项目, 乙)
        self.assertEqual({路.relative_to(甲): 路.read_bytes() for 路 in 甲.rglob("*") if 路.is_file()},
                         {路.relative_to(乙): 路.read_bytes() for 路 in 乙.rglob("*") if 路.is_file()})

    def test_独立异cwd命令行构建(self):
        for 名 in ("核验.py", "预览.py", "静态构建.py"):
            (self.项目 / 名).write_bytes((本目录 / 名).read_bytes())
        输出 = self.新输出()
        运行 = subprocess.run([sys.executable, "-B", str(self.项目 / "静态构建.py"), "--输出", str(输出)],
                              cwd=self.临根, capture_output=True, text=True, timeout=15)
        self.assertEqual(运行.returncode, 0, 运行.stderr)
        self.assertIn("静态构建通过", 运行.stdout)
        self.assertTrue((输出 / "manifest.json").is_file())
        self.assertFalse(list(self.阁根.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
