#!/usr/bin/env python3
"""只将登记入口和书文分页构建到库外临时空目录；Python 3.10+，仅标准库。"""
import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile


本目录 = Path(__file__).resolve().parent
模块说明 = importlib.util.spec_from_file_location("千字文静态共用预览", 本目录 / "预览.py")
预览 = importlib.util.module_from_spec(模块说明)
模块说明.loader.exec_module(预览)


class 构建问题(ValueError):
    pass


def 须(条件, 说明):
    if not 条件:
        raise 构建问题(说明)


def 查输出(输出, 阁根):
    """不创建、不清空目标；只接受库外tmp或CI runner临时目录中的空目录。"""
    路 = Path(输出)
    须(路.is_absolute() and ".." not in 路.parts, "输出须为绝对路径，且不得含上溯分量")
    须(not 路.is_symlink(), "输出目录不得为软链")
    真路 = 路.resolve()
    阁根 = 阁根.resolve()
    须(not 真路.is_relative_to(阁根) and not 阁根.is_relative_to(真路),
       "输出不得位于馆藏内或馆藏祖目录")
    临时根列 = [Path(tempfile.gettempdir()).resolve()]
    if Path("/tmp").is_dir():
        临时根列.append(Path("/tmp").resolve())
    if os.environ.get("RUNNER_TEMP"):
        临时根列.append(Path(os.environ["RUNNER_TEMP"]).resolve())
    须(真路 not in (Path("/").resolve(), Path.home().resolve(), *临时根列), "拒绝危险输出根目录")
    须(any(真路.is_relative_to(根) for 根 in 临时根列), "输出须在系统tmp或RUNNER_TEMP的独立子目录")
    须(真路.is_dir(), "输出须为已存在的空目录")
    须(not any(真路.iterdir()), "输出目录非空；不会覆盖或清空旧产物")
    return 真路


def 读页面(项目):
    页面 = (项目 / "页面").resolve()
    须(页面.is_relative_to(项目), "页面目录软链越出项目")
    结果 = {}
    for 名 in ("index.html", "app.js", "style.css"):
        源 = (页面 / 名).resolve()
        须(源.is_relative_to(页面) and 源.is_file(), "页面文件缺失或软链越界：" + 名)
        结果[名] = 源.read_bytes()
    文 = 结果["index.html"].decode("utf-8")
    须(len(re.findall(r'<meta\b[^>]*\bname=["\']qzw-data-mode["\']', 文)) == 1,
       "index.html须含唯一qzw-data-mode元标签")
    标签式 = r'(<meta\s+name=["\']qzw-data-mode["\']\s+content=["\'])live(["\']\s*/?>)'
    文, 次数 = re.subn(标签式, r'\g<1>static\g<2>', 文)
    须(次数 == 1, "index.html须含唯一qzw-data-mode live元标签")
    结果["index.html"] = 文.encode("utf-8")
    return 结果


def 数据路径(类别, *标识):
    原键 = json.dumps(标识, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"data/{类别}/{hashlib.sha256(原键).hexdigest()}.json"


def 写JSON(输出, 相对, 内容):
    路 = 输出 / 相对
    with 路.open("xb") as 文件:
        文件.write((json.dumps(内容, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))


def 构建(项目, 输出):
    项目 = Path(项目).resolve()
    阁根 = 预览.核.寻阁根(项目 / "静态构建.py")
    输出 = 查输出(输出, 阁根)
    页面 = 读页面(项目)
    索引, 正文 = 预览.查索引(项目, 阁根)
    # 一书只读一次；全部落点先定位通过，才开始向空目标写产物。
    书源 = {号: 预览.核.读源(阁根, 书["路径"]) for 号, 书 in 索引["书目"].items()}
    摘文 = {}
    for 点号, 点 in 索引["落点"].items():
        原文, 源指纹 = 书源[点["书目"]]
        _, _, 起, 止 = 预览.定位(索引, 点号, 原文)
        摘文[点号] = 预览.片段(索引, 点号, 原文, 源指纹, 起, 止)
    # 确认预检期间目标仍为空；所有输出均用排他新建，不覆写已有文件。
    查输出(输出, 阁根)
    (输出 / "data").mkdir()
    (输出 / "data/entry").mkdir()
    (输出 / "data/read").mkdir()
    for 名, 字节 in 页面.items():
        with (输出 / 名).open("xb") as 文件:
            文件.write(字节)
    with (输出 / ".nojekyll").open("xb"):
        pass
    清单 = {"格式": 1, "目录": "data/catalog.json", "入口": {}, "续读": {}}
    写JSON(输出, 清单["目录"], {"正文": 正文, "入口": 索引["入口"]})
    for 入口 in 索引["入口"]:
        路 = 数据路径("entry", 入口["标识"])
        清单["入口"][入口["标识"]] = 路
        写JSON(输出, 路, {"入口": 入口, "落点": [摘文[号] for 号 in 入口["关联"]]})
    for 点号, 点 in 索引["落点"].items():
        原文, 源指纹 = 书源[点["书目"]]
        清单["续读"][点号] = {}
        for 模式 in ("context", "chapter", "book"):
            页表 = 清单["续读"][点号][模式] = {}
            偏移 = 0
            while 偏移 is not None:
                页 = 预览.取分页(索引, 点号, 原文, 源指纹, 模式, 偏移)
                路 = 数据路径("read", 点号, 模式, 偏移)
                页表[str(偏移)] = 路
                写JSON(输出, 路, 页)
                偏移 = 页["后页"]
    # 清单最后落盘；只有全部片段写完，前端才有可消费的发布入口。
    写JSON(输出, "manifest.json", 清单)
    return 清单


def 主程():
    命令 = argparse.ArgumentParser(description=__doc__)
    命令.add_argument("--输出", required=True, help="库外、系统tmp或RUNNER_TEMP下已存在的绝对空目录")
    参数 = 命令.parse_args()
    try:
        清单 = 构建(本目录, 参数.输出)
        页数 = sum(len(页表) for 模式表 in 清单["续读"].values() for 页表 in 模式表.values())
        print(f"静态构建通过：{len(清单['入口'])}入口、{len(清单['续读'])}落点、{页数}续读片。")
        return 0
    except (ValueError, OSError, RuntimeError) as 问题:
        print("静态构建失败：" + str(问题), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(主程())
