#!/usr/bin/env python3
"""只用系统临时微夹具，检验千字文真实HTTP只读协议；不复制整阁。"""
import sys

sys.dont_write_bytecode = True

import copy
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import quote, urlencode


本目录 = Path(__file__).resolve().parent
模块说明 = importlib.util.spec_from_file_location("千字文预览自检", 本目录 / "预览.py")
预览 = importlib.util.module_from_spec(模块说明)
模块说明.loader.exec_module(预览)


def SHA(字节):
    return hashlib.sha256(字节).hexdigest()


class 服务检查(unittest.TestCase):
    def setUp(self):
        self.临时 = tempfile.TemporaryDirectory(prefix="千字文服务自检-")
        self.addCleanup(self.临时.cleanup)
        self.外根 = Path(self.临时.name).resolve()
        self.阁根 = self.外根 / "带空格 改名阁"
        self.项目 = self.阁根 / "房/蒙卷/卷册/千字文"
        self.页面 = self.项目 / "页面"
        self.页面.mkdir(parents=True)
        self.句文 = "𠀀天地玄" + "甲" * 992 + "宇宙洪荒"
        self.正文 = "# 夹具正文\r\n\r\n" + "　".join(self.句文[起:起 + 4] for 起 in range(0, 1000, 4)) + "\r\n"
        self.甲文 = ("# 外一\r\n\r\n## 本篇\r\n\r\n　甲书原字𠀀。  \r\n下一行。\r\n\r\n"
                     + "长行𠀀" * 4200 + "<script>只是原文</script>\r\n\r\n## 次篇\r\n\r\n余文\r\n"
                     + "# 外二\r\n\r\n## 本篇\r\n\r\n重名篇。\r\n\r\n## 次篇\r\n")
        self.乙文 = "# 乙篇\n\n乙书原字。\n\n# 乙后\n尾页。\n"
        self.源 = {"正文.md": self.正文, "甲.md": self.甲文, "乙.md": self.乙文}
        for 名, 文 in self.源.items():
            self.写源(名, 文)
        for 名, 文 in (("index.html", "<!doctype html><p>夹具</p>"), ("app.js", "'use strict';"), ("style.css", "body { color: black; }")):
            (self.页面 / 名).write_text(文, encoding="utf-8")
        # 仅验二进制原样递送，不将微夹具冒充可渲染字体。
        self.字体资源 = {
            "fonts/qzw-rare-214dc.woff2": b"wOF2\x00\xff\x80\r\nfixture-214dc",
            "fonts/OFL.txt": b"SIL OPEN FONT LICENSE Version 1.1\nfixture only\n"}
        (self.页面 / "fonts").mkdir()
        for 名, 字节 in self.字体资源.items():
            (self.页面 / 名).write_bytes(字节)
        (self.页面 / "fonts/未登记字体.woff2").write_bytes(b"not public")
        (self.页面 / "不应开放.txt").write_text("不准递出", encoding="utf-8")
        self.索引 = {"格式": 1, "路径基准": "藏经阁根目录",
            "正文": {"路径": "正文.md", "起锚": "𠀀天地玄", "止锚": "宇宙洪荒", "字数": 1000, "每句字数": 4},
            "书目": {号: {"书名": 号, "路径": f"{号}.md", "内容时代": "夹具", "版本说明": "仅供测试"} for 号 in ("甲", "乙")},
            "落点": {
                "甲段": {"书目": "甲", "篇名": "本篇", "状态": "已接通", "范围": [{"起锚": "# 外一", "止锚": "# 外二"}, {"起锚": "## 本篇", "止锚": "## 次篇"}], "定位摘句": "甲书原字𠀀。", "取文": "所在段", "经注说明": "原样"},
                "乙篇": {"书目": "乙", "篇名": "乙篇", "状态": "已接通", "范围": {"起锚": "# 乙篇", "止锚": "# 乙后"}, "定位摘句": "乙书原字。", "取文": "本篇", "经注说明": "原样"}},
            "入口": [{"标识": f"qzw-{数}", "句段": {"起句": 1, "止句": 数 // 4, "原文": self.句文[:数]}, "导读": "后作导读", "学科": ["蒙学"], "关联": ["甲段", "乙篇"] if 数 == 8 else ["甲段"]} for 数 in (4, 8, 16)]}
        self.写索引()
        self.服务 = 预览.建服务(self.项目, self.阁根, 0)
        self.线程 = threading.Thread(target=self.服务.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.线程.start()
        self.addCleanup(self.停服务)
        self.端口 = self.服务.server_address[1]

    def 停服务(self):
        self.服务.shutdown()
        self.服务.server_close()
        self.线程.join(timeout=2)

    def 写源(self, 名, 文):
        (self.阁根 / 名).write_bytes(文.encode("utf-8"))

    def 写索引(self, 本=None):
        (self.项目 / "关联索引.json").write_text(json.dumps(self.索引 if 本 is None else 本, ensure_ascii=False), encoding="utf-8")

    def 请求(self, 路径, 参数=None, 方法="GET", 头=None):
        路径 = quote(路径, safe="/%?=&+:")
        if 参数 is not None:
            路径 += "?" + urlencode(参数)
        连接 = http.client.HTTPConnection("127.0.0.1", self.端口, timeout=3)
        try:
            连接.request(方法, 路径, headers=头 or {})
            响应 = 连接.getresponse()
            字节 = 响应.read()
            头表 = dict(响应.getheaders())
            内容 = json.loads(字节) if 字节 and 头表.get("Content-Type", "").startswith("application/json") else 字节
            return 响应.status, 头表, 内容
        finally:
            连接.close()

    def 成功(self, 路径, 参数=None):
        状态, 头, 内容 = self.请求(路径, 参数)
        self.assertEqual(状态, 200, 内容)
        self.assertEqual(头["Content-Type"], "application/json; charset=utf-8")
        return 内容

    def 拒绝(self, 状态码, 路径, 参数=None, **选项):
        状态, 头, 内容 = self.请求(路径, 参数, **选项)
        self.assertEqual(状态, 状态码, 内容)
        self.assertEqual(头["Content-Type"], "application/json; charset=utf-8")
        if 选项.get("方法") != "HEAD":
            self.assertEqual(set(内容), {"错误"})
            self.assertTrue(内容["错误"])
        return 内容

    def test_正文活读与四八多句(self):
        正文 = self.成功("/api/catalog")["正文"]
        self.assertEqual(len(正文["句"]), 250)
        self.assertTrue(all(len(句) == 4 for 句 in 正文["句"]))
        self.assertEqual(正文["句"][0], "𠀀天地玄")
        self.assertEqual(正文["SHA256"], SHA(self.正文.encode("utf-8")))
        for 数, 个数 in ((4, 1), (8, 2), (16, 1)):
            内容 = self.成功("/api/entry", {"id": f"qzw-{数}"})
            self.assertEqual(len(内容["入口"]["句段"]["原文"]), 数)
            self.assertEqual(len(内容["落点"]), 个数)
        新正文 = self.正文.replace("甲甲甲甲", "乙甲甲甲", 1)
        self.写源("正文.md", 新正文)
        self.索引["入口"] = self.索引["入口"][:1]
        self.写索引()
        内容 = self.成功("/api/catalog")["正文"]
        self.assertEqual(内容["句"][1], "乙甲甲甲")
        self.assertEqual(内容["SHA256"], SHA(新正文.encode("utf-8")))

    def test_原字行号与源片同快照(self):
        点 = self.成功("/api/entry", {"id": "qzw-4"})["落点"][0]
        self.assertEqual(点["原文"], "　甲书原字𠀀。  \r\n下一行。")
        self.assertEqual((点["起行"], 点["止行"]), (5, 6))
        self.assertEqual(点["源SHA256"], SHA(self.甲文.encode("utf-8")))
        self.assertEqual(点["片段SHA256"], SHA(点["原文"].encode("utf-8")))
        self.写源("甲.md", self.甲文.replace("下一行。", "新一行𠀀。"))
        点 = self.成功("/api/entry", {"id": "qzw-4"})["落点"][0]
        self.assertIn("新一行𠀀。", 点["原文"])
        self.assertNotEqual(点["源SHA256"], SHA(self.甲文.encode("utf-8")))

    def test_三模式长行分页终页逐字拼回(self):
        篇起, 篇止, 段起, 段止 = 预览.定位(self.索引, "甲段", self.甲文)
        for 模式, 范围 in (("context", (max(篇起, 段起 - 800), min(篇止, 段止 + 800))),
                          ("chapter", (篇起, 篇止)), ("book", (0, len(self.甲文)))):
            with self.subTest(模式=模式):
                偏移, 合文, 页数 = 0, "", 0
                源指纹 = SHA(self.甲文.encode("utf-8"))
                while 偏移 is not None:
                    页 = self.成功("/api/read", {"id": "甲段", "mode": 模式, "offset": 偏移, "sha": 源指纹})
                    self.assertLessEqual(len(页["原文"]), 6000)
                    self.assertEqual(页["起字"], 偏移)
                    self.assertEqual(页["止字"] - 页["起字"], len(页["原文"]))
                    self.assertEqual(页["前页"], max(0, 偏移 - 6000) if 偏移 else None)
                    self.assertEqual(页["片段SHA256"], SHA(页["原文"].encode("utf-8")))
                    合文 += 页["原文"]
                    偏移 = 页["后页"]
                    页数 += 1
                self.assertEqual(合文, self.甲文[范围[0]:范围[1]])
                self.assertEqual(页["止字"], 页["总字"])
                if 模式 != "context":
                    self.assertGreaterEqual(页数, 3)
        页 = self.成功("/api/read", {"id": "乙篇", "mode": "book"})
        self.assertIsNone(页["前页"])
        self.assertIsNone(页["后页"])

    def test_变化返回409且不猜锚(self):
        页 = self.成功("/api/read", {"id": "甲段", "mode": "book"})
        self.写源("甲.md", self.甲文.replace("甲书原字𠀀。", "锚已变化。"))
        内容 = self.拒绝(409, "/api/read", {"id": "甲段", "mode": "book", "offset": 6000, "sha": 页["源SHA256"]})
        self.assertIn("重读", 内容["错误"])
        self.拒绝(422, "/api/entry", {"id": "qzw-4"})
        self.拒绝(422, "/api/read", {"id": "甲段", "mode": "book"})

    def test_缺锚重锚边界逆序拒绝(self):
        for 病型 in ("缺锚", "重锚", "范围重现", "逆序"):
            with self.subTest(病型=病型):
                本 = copy.deepcopy(self.索引)
                if 病型 == "缺锚":
                    本["落点"]["甲段"]["定位摘句"] = "不存在的句子"
                elif 病型 == "重锚":
                    self.写源("甲.md", self.甲文.replace("下一行。", "甲书原字𠀀。"))
                elif 病型 == "范围重现":
                    本["落点"]["甲段"]["范围"] = {"起锚": "## 本篇", "止锚": "## 次篇"}
                else:
                    本["落点"]["甲段"]["范围"] = {"起锚": "# 外二", "止锚": "# 外一"}
                self.写索引(本)
                self.拒绝(422, "/api/entry", {"id": "qzw-4"})
                self.写源("甲.md", self.甲文)

    def test_非法参数与未知入口(self):
        for 路径 in ("/api/catalog?foo=1", "/api/catalog?foo", "/api/entry", "/api/entry?id=", "/api/entry?id=qzw-4&id=qzw-4", "/api/entry?id=%FF", "/api/entry?id=%Q0", "/api/read?id=x", "/api/read?id=x&mode=near", "/?x=1"):
            with self.subTest(路径=路径):
                self.拒绝(400, 路径)
        for 值 in ("-1", "1.2", "1e3", "+1", "01", " ", "9" * 100):
            self.拒绝(400, "/api/read", {"id": "甲段", "mode": "book", "offset": 值})
        for 参数 in ({"id": "甲段", "mode": "book", "offset": len(self.甲文)},
                     {"id": "甲段", "mode": "book", "sha": "123"},
                     {"id": "甲段", "mode": "book", "path": "乙.md"}):
            self.拒绝(400, "/api/read", 参数)
        self.拒绝(404, "/api/entry", {"id": "unknown"})
        self.拒绝(404, "/api/read", {"id": "unknown", "mode": "book"})

    def test_馆藏路径越界与软链拒绝(self):
        外件 = self.外根 / "外件.md"
        外件.write_text("不许读", encoding="utf-8")
        (self.阁根 / "软链.md").symlink_to(外件)
        (self.阁根 / "外目录").symlink_to(self.外根, target_is_directory=True)
        for 路 in ("../外件.md", "房/../../外件.md", str(外件), ".", "软链.md",
                   "外目录/外件.md", "缺失.md", "藏经阁/甲.md"):
            with self.subTest(路=路):
                本 = copy.deepcopy(self.索引)
                本["书目"]["甲"]["路径"] = 路
                self.写索引(本)
                self.拒绝(422, "/api/entry", {"id": "qzw-4"})

    def test_内部经及馆内别名从目录到取文均拒绝(self):
        for 序, 内部名 in enumerate(("周易本义-道观正本.md", "周易本义·道观正本.md")):
            self.写源(内部名, self.甲文)
            别名 = f"内部别名{序}.md"
            (self.阁根 / 别名).symlink_to(内部名)
            for 路 in (内部名, 别名):
                with self.subTest(路=路):
                    本 = copy.deepcopy(self.索引)
                    本["书目"]["甲"]["路径"] = 路
                    self.写索引(本)
                    for 接口, 参数 in (("/api/catalog", None),
                                      ("/api/entry", {"id": "qzw-4"}),
                                      ("/api/read", {"id": "甲段", "mode": "book"})):
                        内容 = self.拒绝(422, 接口, 参数)
                        self.assertIn("道观内部经", 内容["错误"])

    def test_外部原书周易本义不误伤(self):
        self.写源("周易本义.md", self.甲文)
        self.索引["书目"]["甲"]["路径"] = "周易本义.md"
        self.写索引()
        self.成功("/api/catalog")
        self.成功("/api/entry", {"id": "qzw-4"})
        self.assertEqual(self.成功("/api/read", {"id": "甲段", "mode": "book"})["原文"], self.甲文[:6000])

    def test_馆内软链可读与根软链信任(self):
        (self.阁根 / "馆内链.md").symlink_to("甲.md")
        本 = copy.deepcopy(self.索引)
        本["书目"]["甲"]["路径"] = "馆内链.md"
        self.写索引(本)
        self.assertEqual(self.成功("/api/read", {"id": "甲段", "mode": "book"})["原文"], self.甲文[:6000])
        根链 = self.外根 / "阁根别名"
        根链.symlink_to(self.阁根, target_is_directory=True)
        self.assertEqual(预览.核.读源(根链, "甲.md"), (self.甲文, SHA(self.甲文.encode("utf-8"))))
        with 预览.建服务(根链 / "房/蒙卷/卷册/千字文", 根链, 0) as 服务:
            self.assertEqual(服务.阁根, self.阁根)
            self.assertEqual(服务.项目, self.项目)

    def test_寻阁根只认固定层级与旧基准拒绝(self):
        self.assertFalse((self.阁根.parent / "AGENTS.md").exists())
        self.assertEqual(预览.核.寻阁根(self.项目 / "预览.py"), self.阁根)
        with 预览.建服务(self.项目) as 服务:
            self.assertEqual(服务.阁根, self.阁根)
        for 源件 in (self.外根 / "预览.py", self.阁根 / "蒙卷/千字文/预览.py",
                     self.阁根 / "房/蒙卷/卷册/其他/预览.py"):
            with self.subTest(源件=源件), self.assertRaises(预览.核.核验问题):
                预览.核.寻阁根(源件)
        本 = copy.deepcopy(self.索引)
        本["路径基准"] = "道观根目录"
        self.写索引(本)
        self.拒绝(422, "/api/catalog")

    def test_非GET拒绝(self):
        for 方法 in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT", "BOGUS"):
            with self.subTest(方法=方法):
                self.拒绝(405, "/api/catalog", 方法=方法)

    def test_本机Host与同源限定(self):
        for 主机 in (f"127.0.0.1:{self.端口}", f"localhost:{self.端口}"):
            状态, _, _ = self.请求("/api/catalog", 头={"Host": 主机, "Origin": "http://" + 主机, "Sec-Fetch-Site": "same-origin"})
            self.assertEqual(状态, 200)
        for 头 in ({"Host": "example.com"}, {"Host": "127.0.0.1:1"}, {"Origin": "https://example.com"},
                   {"Origin": "null"}, {"Origin": f"http://localhost:{self.端口}"}, {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}):
            self.拒绝(403, "/api/catalog", 头=头)
        连接 = http.client.HTTPConnection("127.0.0.1", self.端口, timeout=3)
        try:
            连接.putrequest("GET", "/api/catalog")
            连接.putheader("Host", f"127.0.0.1:{self.端口}")
            连接.endheaders()
            响应 = 连接.getresponse()
            self.assertEqual(响应.status, 403)
            self.assertIn("错误", json.loads(响应.read()))
        finally:
            连接.close()

    def test_静态有限路由类型与安全头(self):
        for 路, 类型 in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css"),
                         ("/fonts/qzw-rare-214dc.woff2", "font/woff2"), ("/fonts/OFL.txt", "text/plain; charset=utf-8")):
            状态, 头, 内容 = self.请求(路)
            self.assertEqual(状态, 200)
            self.assertTrue(头["Content-Type"].startswith(类型))
            self.assertTrue(内容)
            if 路[1:] in self.字体资源:
                self.assertEqual(内容, self.字体资源[路[1:]])
                self.assertEqual(int(头["Content-Length"]), len(内容))
            self.assertEqual(头["Cache-Control"], "no-store")
            self.assertEqual(头["X-Content-Type-Options"], "nosniff")
            self.assertIn("default-src 'none'", 头["Content-Security-Policy"])
            self.assertIn("font-src 'self'", 头["Content-Security-Policy"])
            self.assertNotIn("unsafe-inline", 头["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", 头)
        for 路 in ("/index.html", "/页面/", "/不应开放.txt", "/关联索引.json", "/预览.py", "/../AGENTS.md", "/%2e%2e/AGENTS.md", "/api/file?path=AGENTS.md",
                   "/fonts", "/fonts/", "/fonts/未登记字体.woff2", "/fonts/../style.css", "/fonts/%2e%2e/style.css"):
            self.拒绝(404, 路)

    def test_静态软链不得越界(self):
        外件 = self.外根 / "外页.html"
        外件.write_text("不许读", encoding="utf-8")
        (self.页面 / "index.html").unlink()
        (self.页面 / "index.html").symlink_to(外件)
        self.拒绝(422, "/")

    def test_字体与许可证缺失明确拒绝(self):
        for 名, 字节 in self.字体资源.items():
            with self.subTest(名=名):
                源 = self.页面 / 名
                源.unlink()
                try:
                    self.拒绝(404, "/" + 名)
                finally:
                    源.write_bytes(字节)

    def test_字体与许可证软链不得越界(self):
        外件 = self.外根 / "外资源.bin"
        for 名, 字节 in self.字体资源.items():
            with self.subTest(名=名):
                外件.write_bytes(字节)
                源 = self.页面 / 名
                源.unlink()
                源.symlink_to(外件)
                try:
                    self.拒绝(422, "/" + 名)
                finally:
                    源.unlink()
                    源.write_bytes(字节)

    def test_字体目录软链不得越界(self):
        外目录 = self.外根 / "外字体目录"
        字体目录 = self.页面 / "fonts"
        字体目录.rename(外目录)
        字体目录.symlink_to(外目录, target_is_directory=True)
        for 名 in self.字体资源:
            with self.subTest(名=名):
                self.拒绝(422, "/" + 名)

    def test_损坏索引与异常源编码明报(self):
        (self.项目 / "关联索引.json").write_text('{"格式":1,"格式":1}', encoding="utf-8")
        self.拒绝(422, "/api/catalog")
        self.写索引()
        (self.阁根 / "甲.md").write_bytes(b"\xff")
        self.拒绝(422, "/api/entry", {"id": "qzw-4"})

    def test_只读不落盘且只读所请求书(self):
        前像 = {路.relative_to(self.阁根): 路.read_bytes() for 路 in self.阁根.rglob("*") if 路.is_file()}
        原读 = 预览.核.读源
        读过 = []
        def 记读(根, 相对):
            读过.append(相对)
            return 原读(根, 相对)
        预览.核.读源 = 记读
        try:
            self.成功("/api/catalog")
            self.成功("/api/entry", {"id": "qzw-4"})
            self.成功("/api/read", {"id": "甲段", "mode": "book"})
        finally:
            预览.核.读源 = 原读
        self.assertEqual(set(读过), {"正文.md", "甲.md"})
        后像 = {路.relative_to(self.阁根): 路.read_bytes() for 路 in self.阁根.rglob("*") if 路.is_file()}
        self.assertEqual(前像, 后像)
        self.assertFalse(list(self.阁根.rglob("__pycache__")))

    def test_搬迁异cwd与命令行端口零(self):
        for 名 in ("预览.py", "核验.py"):
            (self.项目 / 名).write_bytes((本目录 / 名).read_bytes())
        进程 = subprocess.Popen([sys.executable, "-B", str(self.项目 / "预览.py"), "--端口", "0"], cwd=self.外根,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as 等待:
                等待.register(进程.stdout, selectors.EVENT_READ)
                self.assertTrue(等待.select(timeout=5), "启动URL未及时输出")
            地址 = 进程.stdout.readline().strip()
            self.assertRegex(地址, r"^http://127\.0\.0\.1:[0-9]+/$")
            端口 = int(地址.split(":")[-1].rstrip("/"))
            连接 = http.client.HTTPConnection("127.0.0.1", 端口, timeout=3)
            try:
                连接.request("GET", "/api/catalog")
                响应 = 连接.getresponse()
                self.assertEqual(响应.status, 200)
                self.assertEqual(len(json.loads(响应.read())["正文"]["句"]), 250)
            finally:
                连接.close()
            进程.send_signal(signal.SIGINT)
            _, 错误 = 进程.communicate(timeout=5)
            self.assertEqual(进程.returncode, 0, 错误)
            self.assertEqual(错误, "")
        finally:
            if 进程.poll() is None:
                进程.kill()
                进程.communicate(timeout=5)
        self.assertFalse(list(self.阁根.rglob("__pycache__")))

    def test_回迁观根无AGENTS仍可命令行启动(self):
        新阁根 = self.外根 / "回迁道观/藏经阁"
        新阁根.parent.mkdir()
        self.阁根.rename(新阁根)
        self.阁根 = 新阁根
        self.项目 = self.阁根 / "房/蒙卷/卷册/千字文"
        self.assertFalse((新阁根.parent / "AGENTS.md").exists())
        self.test_搬迁异cwd与命令行端口零()


if __name__ == "__main__":
    unittest.main(verbosity=2)
