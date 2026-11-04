#!/usr/bin/env python3
"""千字文只读本机预览；Python 3.10+，仅标准库，不生成缓存或日志文件。"""
import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit


本目录 = Path(__file__).resolve().parent
模块说明 = importlib.util.spec_from_file_location("千字文原位核验", 本目录 / "核验.py")
核 = importlib.util.module_from_spec(模块说明)
模块说明.loader.exec_module(核)
每页字数 = 6000


class 请求问题(ValueError):
    def __init__(self, 状态码, 说明):
        super().__init__(说明)
        self.状态码 = 状态码


def 指纹(文字):
    return hashlib.sha256(文字.encode("utf-8")).hexdigest()


def 读正文(索引, 阁根):
    正文 = 索引["正文"]
    核.对象(正文, "路径 起锚 止锚 字数 每句字数", "正文")
    核.须(type(正文["字数"]) is int and 正文["字数"] == 1000, "正文字数须为1000")
    核.须(type(正文["每句字数"]) is int and 正文["每句字数"] == 4, "每句字数须为4")
    原文, 源指纹 = 核.读源(阁根, 正文["路径"])
    起, 止 = 核.限定范围(原文, {键: 正文[键] for 键 in ("起锚", "止锚")}, "正文", True)
    句文 = "".join(原文[起:止].split())
    核.须(len(句文) == 1000, f"正文字数不符：实得{len(句文)}，应为1000")
    return 句文, 源指纹


def 查索引(项目, 阁根):
    """沿用核验器的严格字段与原句规则；书源到实际取文时才读取。"""
    索引路 = (项目 / "关联索引.json").resolve()
    核.须(索引路.is_relative_to(项目.resolve()), "索引软链越出项目")
    索引 = json.loads(索引路.read_bytes().decode("utf-8"), object_pairs_hook=核.无重键)
    核.对象(索引, "格式 路径基准 正文 书目 落点 入口", "索引")
    核.须(type(索引["格式"]) is int and 索引["格式"] == 1, "仅支持格式1")
    核.须(索引["路径基准"] == "藏经阁根目录", "路径基准须为藏经阁根目录")
    句文, 源指纹 = 读正文(索引, 阁根)
    for 名 in ("书目", "落点"):
        核.须(type(索引[名]) is dict and bool(索引[名]), 名 + "须为非空对象")
    for 号, 书 in 索引["书目"].items():
        核.文本(号, "书目标识")
        核.对象(书, "书名 路径 内容时代 版本说明", "书目·" + 号)
        for 键, 值 in 书.items():
            核.文本(值, "书目·" + 号 + "·" + 键)
    for 号, 点 in 索引["落点"].items():
        核.文本(号, "落点标识")
        核.对象(点, "书目 篇名 状态 范围 定位摘句 取文 经注说明", "落点·" + 号)
        for 键 in ("书目", "篇名", "状态", "定位摘句", "取文", "经注说明"):
            核.文本(点[键], "落点·" + 号 + "·" + 键)
        核.须(点["书目"] in 索引["书目"], "落点引用未知书目：" + 号)
        核.须(点["状态"] == "已接通", "落点仅支持已接通状态：" + 号)
        核.须(点["取文"] in ("所在段", "本篇"), "取文只可为所在段或本篇：" + 号)
    核.须(type(索引["入口"]) is list and bool(索引["入口"]), "入口须为非空数组")
    标识集 = set()
    for 入口 in 索引["入口"]:
        核.对象(入口, "标识 句段 导读 学科 关联", "入口")
        for 键 in ("标识", "导读"):
            核.文本(入口[键], "入口·" + 键)
        核.须(入口["标识"] not in 标识集, "入口标识重复：" + 入口["标识"])
        标识集.add(入口["标识"])
        段 = 入口["句段"]
        核.对象(段, "起句 止句 原文", "入口句段")
        起, 止 = 段["起句"], 段["止句"]
        核.须(type(起) is int and type(止) is int and 1 <= 起 <= 止 <= 250,
             "句序须为正文内从1起的连续闭区间")
        核.须(type(段["原文"]) is str and 段["原文"] == 句文[(起 - 1) * 4:止 * 4],
             "入口原句与正文切片不符：" + 入口["标识"])
        for 键 in ("学科", "关联"):
            列 = 入口[键]
            核.须(type(列) is list and bool(列), "入口" + 键 + "须为非空数组")
            for 值 in 列:
                核.文本(值, "入口" + 键)
            核.须(len(set(列)) == len(列), "入口" + 键 + "不得重复")
        核.须(all(号 in 索引["落点"] for 号 in 入口["关联"]), "入口引用未知关联")
    return 索引, {"句": [句文[起:起 + 4] for 起 in range(0, 1000, 4)],
                  "路径": 索引["正文"]["路径"], "SHA256": 源指纹}


def 定位(索引, 点号, 原文):
    点 = 索引["落点"][点号]
    篇起, 篇止 = 核.限定范围(原文, 点["范围"], "落点·" + 点号)
    锚起 = 核.唯一锚(原文, 点["定位摘句"], 篇起, 篇止, "落点·" + 点号 + "定位摘句")
    段起, 段止 = 篇起, 篇止
    if 点["取文"] == "所在段":
        段起, 段止 = 核.所在段(原文, 篇起, 篇止, 锚起, 锚起 + len(点["定位摘句"]), "落点·" + 点号)
    return 篇起, 篇止, 段起, 段止


def 片段(索引, 点号, 原文, 源指纹, 起, 止):
    点 = 索引["落点"][点号]
    书 = 索引["书目"][点["书目"]]
    文 = 原文[起:止]
    return {"标识": 点号, "书名": 书["书名"], "篇名": 点["篇名"], "状态": 点["状态"],
            "版本说明": 书["版本说明"], "内容时代": 书["内容时代"], "经注说明": 点["经注说明"],
            "路径": 书["路径"], "原文": 文, "起行": 原文.count("\n", 0, 起) + 1,
            "止行": 原文.count("\n", 0, max(起, 止 - 1)) + 1,
            "源SHA256": 源指纹, "片段SHA256": 指纹(文)}


def 取分页(索引, 点号, 原文, 源指纹, 模式, 偏移=0):
    """对同一源快照纯取文；本机接口和静态构建共用，不读写文件。"""
    篇起, 篇止, 段起, 段止 = 定位(索引, 点号, 原文)
    if 模式 == "context":
        起, 止 = max(篇起, 段起 - 800), min(篇止, 段止 + 800)
    elif 模式 == "chapter":
        起, 止 = 篇起, 篇止
    else:
        起, 止 = 0, len(原文)
    总字 = 止 - 起
    if not 0 <= 偏移 < 总字:
        raise 请求问题(400, "offset超出当前阅读范围；请从0或返回的前后页位置读取。")
    页止 = min(总字, 偏移 + 每页字数)
    结果 = 片段(索引, 点号, 原文, 源指纹, 起 + 偏移, 起 + 页止)
    结果.update({"模式": 模式, "起字": 偏移, "止字": 页止, "总字": 总字,
                 "前页": max(0, 偏移 - 每页字数) if 偏移 else None,
                 "后页": 页止 if 页止 < 总字 else None})
    return 结果


def 取接口(项目, 阁根, 路径, 参数):
    索引, 正文 = 查索引(项目, 阁根)
    if 路径 == "/api/catalog":
        return {"正文": 正文, "入口": 索引["入口"]}
    if 路径 == "/api/entry":
        入口 = next((项 for 项 in 索引["入口"] if 项["标识"] == 参数["id"]), None)
        if 入口 is None:
            raise 请求问题(404, "未登记入口：" + 参数["id"])
        结果, 书源 = [], {}
        for 点号 in 入口["关联"]:
            书号 = 索引["落点"][点号]["书目"]
            if 书号 not in 书源:
                书源[书号] = 核.读源(阁根, 索引["书目"][书号]["路径"])
            原文, 源指纹 = 书源[书号]
            _, _, 起, 止 = 定位(索引, 点号, 原文)
            结果.append(片段(索引, 点号, 原文, 源指纹, 起, 止))
        return {"入口": 入口, "落点": 结果}
    点号 = 参数["id"]
    if 点号 not in 索引["落点"]:
        raise 请求问题(404, "未登记落点：" + 点号)
    书 = 索引["书目"][索引["落点"][点号]["书目"]]
    原文, 源指纹 = 核.读源(阁根, 书["路径"])
    if "sha" in 参数 and 参数["sha"] != 源指纹:
        raise 请求问题(409, "馆藏源文已变化；请重新打开入口，从当前版本重读，不续接旧页。")
    return 取分页(索引, 点号, 原文, 源指纹, 参数["mode"], int(参数.get("offset", "0")))


静态路 = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
接口参数 = {"/api/catalog": (set(), set()),
            "/api/entry": ({"id"}, {"id"}),
            "/api/read": ({"id", "mode"}, {"id", "mode", "offset", "sha"})}


class 只读请求(BaseHTTPRequestHandler):
    server_version = "QianziPreview"
    sys_version = ""

    def log_message(self, 格式, *参数):
        pass

    def 应答(self, 状态, 内容, 类型="application/json; charset=utf-8"):
        if not isinstance(内容, bytes):
            内容 = json.dumps(内容, ensure_ascii=False).encode("utf-8")
        self.send_response(状态)
        self.send_header("Content-Type", 类型)
        self.send_header("Content-Length", str(len(内容)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if 状态 == 405:
            self.send_header("Allow", "GET")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(内容)

    def send_error(self, code, message=None, explain=None):
        状态 = 405 if code == 501 else code
        self.close_connection = True
        self.应答(状态, {"错误": "仅允许GET只读请求" if 状态 == 405 else "HTTP请求无效"})

    def 同源(self):
        主机列 = self.headers.get_all("Host", [])
        端口 = self.server.server_address[1]
        允许 = {f"127.0.0.1:{端口}", f"localhost:{端口}"}
        if 端口 == 80:
            允许.update({"127.0.0.1", "localhost"})
        if len(主机列) != 1 or 主机列[0].lower() not in 允许:
            raise 请求问题(403, "仅接受本机回环地址的Host")
        来源列 = self.headers.get_all("Origin", [])
        if 来源列 and (len(来源列) != 1 or 来源列[0].lower() != "http://" + 主机列[0].lower()):
            raise 请求问题(403, "拒绝跨源请求；请从启动时显示的本机页面阅读")
        取源列 = self.headers.get_all("Sec-Fetch-Site", [])
        if 取源列 and (len(取源列) != 1 or 取源列[0] not in ("same-origin", "none")):
            raise 请求问题(403, "拒绝跨源页面发起的读取")

    def do_GET(self):
        try:
            self.同源()
            地址 = urlsplit(self.path)
            if not self.path.startswith("/") or 地址.scheme or 地址.netloc or 地址.fragment:
                raise 请求问题(400, "请求地址须为本机相对路由")
            路径 = 地址.path
            if 路径 not in 静态路 and 路径 not in 接口参数:
                raise 请求问题(404, "未登记的阅读路由")
            if re.search(r"%(?![0-9A-Fa-f]{2})", 地址.query):
                raise 请求问题(400, "参数百分号编码不完整")
            try:
                键值列 = parse_qsl(地址.query, keep_blank_values=True, strict_parsing=True,
                                  encoding="utf-8", errors="strict", max_num_fields=8)
            except (ValueError, UnicodeError) as 问题:
                raise 请求问题(400, "参数编码或格式无效") from 问题
            参数 = dict(键值列)
            if len(参数) != len(键值列):
                raise 请求问题(400, "拒绝重复参数")
            必有, 可有 = 接口参数.get(路径, (set(), set()))
            if not 必有 <= 参数.keys() or not 参数.keys() <= 可有 or any(not 值 for 值 in 参数.values()):
                raise 请求问题(400, "参数缺失、多余或为空")
            if 路径 == "/api/read":
                if 参数["mode"] not in ("context", "chapter", "book"):
                    raise 请求问题(400, "mode只可为context、chapter或book")
                if "offset" in 参数 and not re.fullmatch(r"0|[1-9][0-9]{0,14}", 参数["offset"]):
                    raise 请求问题(400, "offset须为非负十进制整数")
                if "sha" in 参数 and not re.fullmatch(r"[0-9a-f]{64}", 参数["sha"]):
                    raise 请求问题(400, "sha须为源SHA256的64位小写十六进制")
            if 路径 in 静态路:
                名, 类型 = 静态路[路径]
                页面 = (self.server.项目 / "页面").resolve()
                真路 = (页面 / 名).resolve()
                if not 页面.is_relative_to(self.server.项目.resolve()) or not 真路.is_relative_to(页面):
                    raise 请求问题(422, "页面软链越出授权目录")
                if not 真路.is_file():
                    raise 请求问题(404, "页面资源尚未就绪")
                self.应答(200, 真路.read_bytes(), 类型)
            else:
                self.应答(200, 取接口(self.server.项目, self.server.阁根, 路径, 参数))
        except 请求问题 as 问题:
            self.应答(问题.状态码, {"错误": str(问题)})
        except (核.核验问题, OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as 问题:
            self.应答(422, {"错误": "定位失效待修：" + str(问题)})
        except ValueError as 问题:
            self.应答(400, {"错误": "请求参数无效：" + str(问题)})

    def 拒写(self):
        self.close_connection = True
        self.应答(405, {"错误": "仅允许GET只读请求"})

    do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = 拒写


def 建服务(项目=None, 阁根=None, 端口=0):
    项目 = Path(项目).resolve() if 项目 is not None else 本目录
    阁根 = Path(阁根).resolve() if 阁根 is not None else 核.寻阁根(项目 / "预览.py")
    服务 = ThreadingHTTPServer(("127.0.0.1", 端口), 只读请求)
    服务.daemon_threads = True
    服务.项目, 服务.阁根 = 项目, 阁根
    return 服务


def 主程():
    命令 = argparse.ArgumentParser(description=__doc__)
    命令.add_argument("--端口", type=int, default=8765, help="本机端口；0为系统自动分配（默认8765）")
    参数 = 命令.parse_args()
    if not 0 <= 参数.端口 <= 65535:
        命令.error("端口须在0—65535之间")
    try:
        with 建服务(端口=参数.端口) as 服务:
            print(f"http://127.0.0.1:{服务.server_address[1]}/", flush=True)
            try:
                服务.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                pass
        return 0
    except OSError as 问题:
        print("预览未启动：" + str(问题), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(主程())
