"use strict";

const 取 = (名) => document.getElementById(名);
const 页面根 = new URL(".", window.location.href);
const 静态 = document.querySelector('meta[name="qzw-data-mode"]')?.content === "static";
const 是对象 = (值) => 值 !== null && typeof 值 === "object" && !Array.isArray(值);
const 自有 = (对象, 键) => 是对象(对象) && Object.prototype.hasOwnProperty.call(对象, 键);
let 清单就绪;
const 状态 = {目录: null, 入口: null, 落点: [], 所选: null, 阅读: null, 起钮: null, 请求号: 0, 阅读号: 0, 只看: false, 须重读: false};
const 模式名 = {excerpt: "相关原段", context: "篇内上下文", chapter: "本篇范围", book: "全书分片"};

function 节点(标签, 内容, 类) {
  const 元 = document.createElement(标签);
  if (内容 !== undefined) 元.textContent = 内容;
  if (类) 元.className = 类;
  return 元;
}

function 报错(名, 消息) {
  取(名).textContent = 消息 || "";
  取(名).hidden = !消息;
}

async function 取数据(路径, 参数 = {}) {
  const 地址 = new URL(路径, 页面根);
  for (const [键, 值] of Object.entries(参数)) if (值 !== undefined) 地址.searchParams.set(键, 值);
  let 应答;
  try { 应答 = await fetch(地址, {cache: "no-store", credentials: "omit", redirect: "error"}); }
  catch { throw new Error(静态 ? "未能读取馆藏快照，请检查网络后重试；不会转接本机服务。" : "无法连接本地服务，请确认预览服务仍在运行。"); }
  if (!应答.ok && 静态) throw new Error(`馆藏快照读取失败（${应答.status}），请检查发布是否完整。`);
  let 数据;
  try { 数据 = await 应答.json(); }
  catch { throw new Error(静态 ? "馆藏快照没有递回可读的 JSON 数据，请检查发布是否完整。" : "本地服务没有递回可读数据，请确认预览服务仍在运行。"); }
  if (!应答.ok) throw new Error(数据.错误 || `读取失败（${应答.status}）`);
  return 数据;
}

function 查文件(路径, 类别) {
  const 格式 = 类别 === "entry" ? /^data\/entry\/[0-9a-f]+\.json$/ : /^data\/read\/[0-9a-f]+\.json$/;
  if (typeof 路径 !== "string" || !格式.test(路径)) throw new Error("馆藏快照的文件映射无效；只读取清单登记的 data 文件。");
  return 路径;
}

function 查清单(清单) {
  if (!是对象(清单) || 清单.格式 !== 1 || 清单.目录 !== "data/catalog.json" || !是对象(清单.入口) || !是对象(清单.续读)) {
    throw new Error("馆藏快照清单格式无效。");
  }
  for (const 路径 of Object.values(清单.入口)) 查文件(路径, "entry");
  for (const 点 of Object.values(清单.续读)) {
    for (const 模式 of ["context", "chapter", "book"]) {
      if (!是对象(点) || !自有(点[模式], "0")) throw new Error("馆藏快照缺少阅读模式的起始页。");
      for (const [位, 路径] of Object.entries(点[模式])) {
        if (!/^(0|[1-9][0-9]*)$/.test(位) || !Number.isSafeInteger(Number(位))) throw new Error("馆藏快照的分页位置无效。");
        查文件(路径, "read");
      }
    }
  }
  return 清单;
}

async function 读取(路径, 参数 = {}) {
  if (!静态) return 取数据(路径.replace(/^\//, ""), 参数);
  const 清单 = await (清单就绪 ||= 取数据("manifest.json").then(查清单));
  if (路径 === "/api/catalog") return 取数据(清单.目录);
  if (路径 === "/api/entry") {
    if (!自有(清单.入口, 参数.id)) throw new Error("馆藏快照未登记这一入口。");
    const 数据 = await 取数据(查文件(清单.入口[参数.id], "entry"));
    if (!是对象(数据) || 数据.入口?.标识 !== 参数.id || !Array.isArray(数据.落点)) throw new Error("馆藏快照的入口数据与清单不符。");
    return 数据;
  }
  if (路径 === "/api/read") {
    if (!自有(清单.续读, 参数.id)) throw new Error("馆藏快照未登记这一阅读落点。");
    if (!["context", "chapter", "book"].includes(参数.mode)) throw new Error("馆藏快照未登记这一阅读模式。");
    const 位 = String(参数.offset === undefined ? 0 : 参数.offset);
    if (!/^(0|[1-9][0-9]*)$/.test(位) || !Number.isSafeInteger(Number(位))) throw new Error("分页位置须为非负整数。");
    const 分页 = 清单.续读[参数.id][参数.mode];
    if (!自有(分页, 位)) throw new Error("馆藏快照未登记这一页，请重新打开入口；不会改读其他页面。");
    const 数据 = await 取数据(查文件(分页[位], "read"));
    if (!是对象(数据) || 数据.标识 !== 参数.id || 数据.模式 !== 参数.mode || 数据.起字 !== Number(位)) throw new Error("馆藏快照的阅读页与清单不符。");
    if (参数.sha !== undefined && 数据.源SHA256 !== 参数.sha) throw new Error("馆藏源文已变化；请刷新页面后重新打开入口，不续接旧页。");
    return 数据;
  }
  throw new Error("未登记的馆藏快照读取方式。");
}

function 入口钮(入口, 类, 小号) {
  const 钮 = 节点("button", undefined, 类);
  钮.type = "button";
  钮.dataset.entry = 入口.标识;
  钮.setAttribute("aria-pressed", "false");
  钮.setAttribute("aria-controls", "reader");
  if (小号) 钮.append(节点("small", 小号));
  钮.append(节点("span", 类 === "join" ? "合读 ↗" : 入口.句段.原文));
  if (类 === "join") 钮.setAttribute("aria-label", "合读“" + 入口.句段.原文 + "”");
  钮.addEventListener("click", () => 开入口(入口.标识, 钮, true));
  return 钮;
}

function 排全文() {
  const 目录 = 状态.目录;
  const 四字 = new Map(目录.入口.filter(项 => 项.句段.起句 === 项.句段.止句).map(项 => [项.句段.起句, 项]));
  const 八字 = new Map(目录.入口.filter(项 => 项.句段.止句 === 项.句段.起句 + 1).map(项 => [项.句段.起句, 项]));
  const 卷 = document.createDocumentFragment();
  for (let 位 = 0; 位 < 目录.正文.句.length; 位 += 2) {
    const 行 = 节点("div", undefined, "couplet");
    行.id = "line-" + (位 + 1);
    行.dataset.start = String(位 + 1);
    行.dataset.end = String(Math.min(位 + 2, 目录.正文.句.length));
    行.dataset.linked = String(四字.has(位 + 1) || 四字.has(位 + 2) || 八字.has(位 + 1));
    行.append(节点("span", String(位 / 2 + 1).padStart(3, "0"), "line-no"));
    for (let 句位 = 位; 句位 < Math.min(位 + 2, 目录.正文.句.length); 句位++) {
      const 入口 = 四字.get(句位 + 1);
      行.append(入口 ? 入口钮(入口, "verse verse-button") : 节点("span", 目录.正文.句[句位], "verse"));
    }
    if (八字.has(位 + 1)) 行.append(入口钮(八字.get(位 + 1), "join"));
    卷.append(行);
  }
  取("poem").replaceChildren(卷);
  取("shortcuts").replaceChildren(...[...四字.values()].map(项 => 入口钮(项, "shortcut", String(项.句段.起句).padStart(3, "0"))));
  取("poem-source").textContent = `${目录.正文.路径}\n源文件 SHA256：${目录.正文.SHA256}`;
  取("page-status").textContent = `全文 ${目录.正文.句.length} 句 · ${四字.size} 处四字导读 · 八字合读可分别入书`;
}

function 标当前() {
  const 入口 = 状态.入口;
  document.querySelectorAll("[data-entry]").forEach(钮 => 钮.setAttribute("aria-pressed", String(!!入口 && 钮.dataset.entry === 入口.标识)));
  document.querySelectorAll(".couplet").forEach(行 => {
    行.hidden = 状态.只看 && 行.dataset.linked !== "true";
    行.classList.toggle("active", !!入口 && Number(行.dataset.start) <= 入口.句段.止句 && Number(行.dataset.end) >= 入口.句段.起句);
  });
}

function 书签钮(点, 落点) {
  const 同书多篇 = 落点.filter(另一点 => 另一点.书名 === 点.书名).length > 1;
  const 书签名 = "《" + 点.书名 + "》" + (同书多篇 ? " · " + 点.篇名 : "");
  const 钮 = 节点("button", 书签名, "book-tab");
  钮.type = "button";
  钮.dataset.point = 点.标识;
  钮.setAttribute("aria-pressed", "false");
  钮.setAttribute("aria-controls", "book");
  钮.addEventListener("click", () => 选书(点));
  return 钮;
}

function 排书签(入口, 落点) {
  const 书签栏 = 取("book-tabs");
  const 分组 = Array.isArray(入口.分读) && 入口.分读.length > 0;
  书签栏.classList.toggle("grouped", 分组);
  书签栏.setAttribute("aria-label", 分组 ? "按分读选择关联原段" : "选择关联书籍");
  if (!分组) {
    书签栏.replaceChildren(...落点.map(点 => 书签钮(点, 落点)));
    return 落点[0];
  }
  const 点表 = new Map(落点.map(点 => [点.标识, 点]));
  let 首点;
  书签栏.replaceChildren(...入口.分读.map((分读, 位) => {
    const 组点 = (Array.isArray(分读.关联) ? 分读.关联 : []).map(标识 => 点表.get(标识)).filter(Boolean);
    if (!首点 && 组点.length) 首点 = 组点[0];
    const 组 = 节点("div", undefined, "phrase-group");
    const 题 = 节点("h3", `${分读.原文} · ${组点.length ? "已挂钩" : "待寻原段"}`, "phrase-title");
    题.id = "phrase-title-" + 位;
    组.setAttribute("role", "group");
    组.setAttribute("aria-labelledby", 题.id);
    组.append(题);
    if (分读.说明) {
      const 说明 = 节点("p", 分读.说明, "phrase-note");
      说明.id = "phrase-note-" + 位;
      组.setAttribute("aria-describedby", 说明.id);
      组.append(说明);
    }
    if (组点.length) {
      const 按钮栏 = 节点("div", undefined, "phrase-book-tabs");
      按钮栏.append(...组点.map(点 => 书签钮(点, 落点)));
      组.append(按钮栏);
    }
    return 组;
  }));
  return 首点;
}

async function 开入口(标识, 起钮, 跳转) {
  const 轮 = ++状态.请求号;
  ++状态.阅读号;
  状态.起钮 = 起钮 || 状态.起钮;
  状态.入口 = 状态.目录.入口.find(项 => 项.标识 === 标识);
  状态.落点 = [];
  状态.所选 = null;
  取("entry").hidden = true;
  取("book").hidden = true;
  取("reader-empty").hidden = true;
  取("reload").hidden = true;
  取("return").disabled = false;
  报错("entry-error", "");
  标当前();
  取("read-status").textContent = 静态 ? "正在读取馆藏快照……" : "正在按原位读取……";
  取("reader").setAttribute("aria-busy", "true");
  if (跳转 && window.matchMedia("(max-width: 720px)").matches) 取("reader").scrollIntoView({block: "start"});
  try {
    const 数据 = await 读取("/api/entry", {id: 标识});
    if (轮 !== 状态.请求号) return;
    状态.入口 = 数据.入口;
    状态.落点 = 数据.落点;
    状态.须重读 = false;
    document.querySelectorAll("[data-mode]").forEach(钮 => { 钮.disabled = false; });
    取("entry-title").textContent = 数据.入口.句段.原文;
    取("entry-tags").replaceChildren(...数据.入口.学科.map(项 => 节点("span", 项)));
    取("guide").textContent = 数据.入口.导读;
    const 首点 = 排书签(数据.入口, 数据.落点);
    取("entry").hidden = false;
    if (首点) 选书(首点);
    else {
      取("read-status").textContent = "尚待接通原段";
      报错("entry-error", "这一入口尚未接通书篇，暂不展示原文。");
    }
    if (跳转 && window.matchMedia("(max-width: 720px)").matches) 取("entry-title").focus({preventScroll: true});
  } catch (错) {
    if (轮 !== 状态.请求号) return;
    报错("entry-error", "本次未能取文：" + 错.message);
    取("reload").hidden = false;
  } finally {
    if (轮 === 状态.请求号) 取("reader").setAttribute("aria-busy", "false");
  }
}

function 选书(点) {
  if (状态.须重读) return;
  ++状态.阅读号;
  状态.所选 = 点;
  取("book").hidden = false;
  取("book-title").textContent = "《" + 点.书名 + "》";
  取("chapter-title").textContent = 点.篇名;
  取("source-note").textContent = 点.经注说明;
  document.querySelectorAll("[data-point]").forEach(钮 => 钮.setAttribute("aria-pressed", String(钮.dataset.point === 点.标识)));
  显原文(点, "excerpt");
}

function 显原文(资料, 模式) {
  状态.阅读 = {资料, 模式};
  取("chapter-title").textContent = 模式 === "book" ? "全书 · 馆藏文件分片" : 资料.篇名;
  取("source-note").textContent = 模式 === "book"
    ? "当前从馆藏文件书首分片阅读，不只限于原入口的篇段。版本及经注说明见下方凭据。"
    : 模式 === "chapter" ? "按登记的篇界展开，范围可能大于入口相关段。经传与注释照原书连排，不把整段统称古经；详见下方版本与经注说明。" : 资料.经注说明;
  报错("read-error", "");
  取("reload").hidden = true;
  取("original").textContent = 资料.原文;
  取("original").scrollTop = 0;
  取("original").hidden = false;
  document.querySelectorAll("[data-mode]").forEach(钮 => 钮.setAttribute("aria-pressed", String(钮.dataset.mode === 模式)));
  取("read-status").textContent = `${模式名[模式]} · 源文件第 ${资料.起行}—${资料.止行} 行`;
  const 可前 = Number.isInteger(资料.前页), 可后 = Number.isInteger(资料.后页);
  取("pagination").hidden = !(可前 || 可后);
  取("previous").disabled = !可前;
  取("next").disabled = !可后;
  取("page-number").textContent = 模式 === "excerpt" ? "" : `${资料.起字 + 1}—${资料.止字} / ${资料.总字} 字符`;
  const 表 = document.createDocumentFragment();
  for (const [题, 值] of [["内容时代", 资料.内容时代], ["馆藏版本", 资料.版本说明], ["经传与注释", 资料.经注说明], ["原位路径", 资料.路径], ["源文件 SHA256", 资料.源SHA256], ["当前片段 SHA256", 资料.片段SHA256]]) {
    表.append(节点("dt", 题), 节点("dd", 值));
  }
  取("metadata").replaceChildren(表);
}

async function 续读(模式, 位 = 0) {
  if (!状态.所选 || 状态.须重读) return;
  const 点 = 状态.所选;
  const 轮 = ++状态.阅读号;
  const 原焦点 = document.activeElement;
  const 从分页来 = 原焦点 === 取("previous") || 原焦点 === 取("next");
  if (模式 === "excerpt") { 显原文(点, 模式); return; }
  取("original").hidden = true;
  取("pagination").hidden = true;
  报错("read-error", "");
  取("read-status").textContent = "正在读取" + 模式名[模式] + "……";
  try {
    const 资料 = await 读取("/api/read", {id: 点.标识, mode: 模式, offset: 位, sha: 点.源SHA256});
    if (轮 !== 状态.阅读号) return;
    显原文(资料, 模式);
    if (从分页来) {
      const 回焦点 = !原焦点.disabled && !取("pagination").hidden ? 原焦点 : 取("original");
      回焦点.focus({preventScroll: true});
    }
  } catch (错) {
    if (轮 !== 状态.阅读号) return;
    取("original").textContent = "";
    取("read-status").textContent = "本次未交原文";
    报错("read-error", 错.message);
    状态.须重读 = true;
    状态.所选 = null;
    状态.落点 = [];
    document.querySelectorAll("[data-mode], [data-point]").forEach(钮 => { 钮.disabled = true; });
    取("reload").hidden = false;
    if (从分页来) 取("reload").focus({preventScroll: true});
  }
}

取("filter").addEventListener("click", () => {
  状态.只看 = !状态.只看;
  取("filter").setAttribute("aria-pressed", String(状态.只看));
  取("filter").textContent = 状态.只看 ? "回到全文" : "只看导读";
  标当前();
});
document.querySelectorAll("[data-mode]").forEach(钮 => 钮.addEventListener("click", () => 续读(钮.dataset.mode)));
取("previous").addEventListener("click", () => { if (Number.isInteger(状态.阅读?.资料.前页)) 续读(状态.阅读.模式, 状态.阅读.资料.前页); });
取("next").addEventListener("click", () => { if (Number.isInteger(状态.阅读?.资料.后页)) 续读(状态.阅读.模式, 状态.阅读.资料.后页); });
取("reload").addEventListener("click", () => { if (状态.入口) 开入口(状态.入口.标识, 状态.起钮, false); });
取("return").addEventListener("click", () => {
  ++状态.请求号; ++状态.阅读号;
  const 入口 = 状态.入口;
  取("entry").hidden = true;
  取("reader-empty").hidden = false;
  取("reader").setAttribute("aria-busy", "false");
  取("reload").hidden = true;
  报错("entry-error", "");
  状态.入口 = null;
  状态.所选 = null;
  取("return").disabled = true;
  标当前();
  if (入口) {
    const 行 = 取("line-" + (入口.句段.起句 - ((入口.句段.起句 - 1) % 2)));
    const 钮 = 行?.querySelector(`[data-entry="${入口.标识}"]`) || 状态.起钮;
    行?.scrollIntoView({block: "center"});
    钮?.focus({preventScroll: true});
  }
});

(async () => {
  if (静态) {
    取("data-kind").textContent = "馆藏快照 · 只读";
    取("snapshot-note").hidden = false;
    取("book-stamp").textContent = "馆藏快照";
    取("page-status").textContent = "正在读取馆藏快照索引……";
  }
  try {
    状态.目录 = await 读取("/api/catalog");
    排全文();
    if (状态.目录.入口.length) await 开入口(状态.目录.入口[0].标识, null, false);
  } catch (错) {
    取("page-status").textContent = "暂未载入";
    报错("page-error", 静态 ? "无法读取馆藏快照索引：" + 错.message : "无法读取本地索引：" + 错.message + " 可在预览服务启动后刷新页面重试。");
  }
})();
