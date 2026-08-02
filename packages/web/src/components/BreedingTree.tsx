import { App, Button, Space, Tooltip } from "antd";
import { CopyOutlined, PictureOutlined } from "@ant-design/icons";
import { toPng } from "html-to-image";
import { useRef } from "react";
import type { PalProfile } from "../types";

export type SelectedPair = {
  child_pal_id: string;
  parent_a_id: string;
  parent_a_name: string;
  parent_b_id: string;
  parent_b_name: string;
  method: string;
  depth: number;
};

type Props = {
  targetPal: string | null;
  selectedPairs: SelectedPair[];
  palNameToId: Record<string, string>;
  palProfiles: Record<string, PalProfile>;
};

function resolveProfile(
  token: string,
  palNameToId: Record<string, string>,
  palProfiles: Record<string, PalProfile>,
): PalProfile | undefined {
  if (palProfiles[token]) return palProfiles[token];
  const id = palNameToId[token];
  if (id && palProfiles[id]) return palProfiles[id];
  for (const profile of Object.values(palProfiles)) {
    if (profile.cn_name === token || profile.id === token) {
      return profile;
    }
  }
  return undefined;
}

function PalNode({
  token,
  palNameToId,
  palProfiles,
  pairByChild,
  isRoot = false,
  visited,
}: {
  token: string;
  palNameToId: Record<string, string>;
  palProfiles: Record<string, PalProfile>;
  pairByChild: Map<string, SelectedPair>;
  isRoot?: boolean;
  visited?: Set<string>;
}) {
  const profile = resolveProfile(token, palNameToId, palProfiles);
  const displayName = profile?.cn_name ?? token;
  const pair = pairByChild.get(token);
  // 路径级防循环：同种配种（same_species，如 空涡龙+空涡龙）会 self-reference，
  // 若不记录已访问节点会无限递归导致浏览器崩溃。
  const path = visited ? new Set(visited) : new Set<string>();
  path.add(token);

  return (
    <li>
      <div className={`breed-node-card${isRoot ? " breed-node-root-card" : ""}`}>
        {profile?.image_url ? (
          <img className="pal-inline-avatar breed-avatar" src={profile.image_url} alt="" aria-hidden="true" />
        ) : (
          <span className="pal-inline-avatar pal-inline-avatar-fallback breed-avatar">
            {displayName.slice(0, 1)}
          </span>
        )}
        <span>{displayName}</span>
        {isRoot && <span className="breed-root-tag">目标</span>}
      </div>
      {pair && (
        <ul>
          {!path.has(pair.parent_a_id) && (
            <PalNode
              token={pair.parent_a_id}
              palNameToId={palNameToId}
              palProfiles={palProfiles}
              pairByChild={pairByChild}
              visited={path}
            />
          )}
          {!path.has(pair.parent_b_id) && (
            <PalNode
              token={pair.parent_b_id}
              palNameToId={palNameToId}
              palProfiles={palProfiles}
              pairByChild={pairByChild}
              visited={path}
            />
          )}
        </ul>
      )}
    </li>
  );
}

/** 把配种树转成可粘贴的文本（微信友好）。 */
function buildRouteText(
  rootToken: string,
  pairByChild: Map<string, SelectedPair>,
  palNameToId: Record<string, string>,
  palProfiles: Record<string, PalProfile>,
): string {
  const lines: string[] = [];
  const resolveName = (token: string): string => {
    const profile = resolveProfile(token, palNameToId, palProfiles);
    return profile?.cn_name ?? token;
  };

  const visit = (childToken: string, indent: number, seen: Set<string> = new Set()) => {
    const pair = pairByChild.get(childToken);
    const childName = resolveName(childToken);
    // 防循环：同种配种 self-reference（如 空涡龙+空涡龙）会无限递归
    if (!pair || seen.has(childToken)) {
      lines.push(`${"  ".repeat(indent)}${childName}`);
      return;
    }
    const a = resolveName(pair.parent_a_id);
    const b = resolveName(pair.parent_b_id);
    const prefix = indent === 0 ? "" : `${"  ".repeat(indent)}└─ `;
    lines.push(`${prefix}${childName} = ${a} + ${b}`);
    const nextSeen = new Set(seen).add(childToken);
    visit(pair.parent_a_id, indent + 1, nextSeen);
    visit(pair.parent_b_id, indent + 1, nextSeen);
  };

  visit(rootToken, 0);
  return lines.join("\n");
}

export function BreedingTree({ targetPal, selectedPairs, palNameToId, palProfiles }: Props) {
  const treeRef = useRef<HTMLDivElement | null>(null);
  const { message } = App.useApp();

  const pairByChild = new Map<string, SelectedPair>();
  for (const pair of selectedPairs) {
    pairByChild.set(pair.child_pal_id, pair);
  }

  const rootToken = targetPal ?? pairByChild.keys().next().value as string | undefined;

  if (!rootToken || !pairByChild.has(rootToken)) {
    return (
      <div className="breed-tree-empty">
        确认一组父母后，这里会展示纵向配种二叉树。
      </div>
    );
  }

  const rootName = resolveProfile(rootToken, palNameToId, palProfiles)?.cn_name ?? rootToken;
  const rootTokenSafe: string = rootToken;

  async function copyText() {
    const text = buildRouteText(rootTokenSafe, pairByChild, palNameToId, palProfiles);
    const content = `【${rootName} 配种路线】\n${text}`;
    try {
      await navigator.clipboard.writeText(content);
      message.success("配种路线已复制，可粘贴到微信发送");
      return;
    } catch {
      // 非安全上下文（http 线上部署）navigator.clipboard 不可用 → 回退 execCommand
      try {
        const ta = document.createElement("textarea");
        ta.value = content;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        message.success("配种路线已复制，可粘贴到微信发送");
      } catch {
        message.error("复制失败，请手动选择文本");
      }
    }
  }

  /** 把 CDN/跨域头像换成 dataURL，供 html-to-image 无 CORS 渲染。
   *  - cdn.paldb.cc（旧）：走 /agent/pal-image 代理
   *  - resource-palworld.tc-imba.com（tc-imba 新）：有 CORS(Allow-Origin:*)，直接 fetch 转 dataURL
   */
  async function embedImages(node: HTMLElement): Promise<() => void> {
    const imgs = Array.from(node.querySelectorAll<HTMLImageElement>("img"));
    const tasks = imgs.map(async (img) => {
      const src = img.getAttribute("src") ?? "";
      if (!src.includes("cdn.paldb.cc") && !src.includes("resource-palworld.tc-imba.com")) {
        return;
      }
      let dataUrl: string | null = null;
      try {
        if (src.includes("cdn.paldb.cc")) {
          const match = src.match(/\/T_([^/]+?)_icon_normal\.webp$/);
          if (match) {
            const res = await fetch(`/agent/pal-image/${match[1]}`);
            if (res.ok) dataUrl = await blobToDataUrl(await res.blob());
          }
        } else {
          const res = await fetch(src);
          if (res.ok) dataUrl = await blobToDataUrl(await res.blob());
        }
      } catch {
        // 保持原样
      }
      if (dataUrl) {
        const original = src;
        img.setAttribute("src", dataUrl);
        img.setAttribute("data-original-src", original);
      }
    });
    await Promise.all(tasks);
    return () => {
      imgs.forEach((img) => {
        const original = img.getAttribute("data-original-src");
        if (original) {
          img.setAttribute("src", original);
          img.removeAttribute("data-original-src");
        }
      });
    };
  }

  function blobToDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async function copyImage() {
    const node = treeRef.current;
    if (!node) return;
    const restore = await embedImages(node);
    try {
      const dataUrl = await toPng(node, {
        pixelRatio: 2,
        backgroundColor: "#ffffff",
        cacheBust: true,
        // 导出时排除操作按钮容器，避免「复制/图片」出现在生成的图片里
        filter: (el) => !(el instanceof HTMLElement && el.classList.contains("breed-tree-actions")),
      });
      const blob = await (await fetch(dataUrl)).blob();
      // 优先用 ClipboardItem 复制图片到剪贴板
      try {
        if (typeof ClipboardItem !== "undefined") {
          await navigator.clipboard.write([
            new ClipboardItem({ "image/png": blob }),
          ]);
          message.success("配种路线图片已复制，可粘贴到微信发送");
          return;
        }
      } catch {
        // 剪贴板写图片失败，退化为下载
      }
      // 退化：下载图片
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${rootName}-配种路线.png`;
      a.click();
      message.success("图片已下载（浏览器不支持直接复制图片）");
    } catch {
      message.error("生成图片失败");
    } finally {
      restore();
    }
  }

  return (
    <div className="breed-tree" ref={treeRef}>
      <div className="breed-tree-head">
        <h3 className="breed-tree-title">已确认配种路径</h3>
        <Space size={4} className="breed-tree-actions">
          <Tooltip title="复制配种路线为文字">
            <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => void copyText()}>
              复制
            </Button>
          </Tooltip>
          <Tooltip title="把配种树导出为图片">
            <Button size="small" type="text" icon={<PictureOutlined />} onClick={() => void copyImage()}>
              图片
            </Button>
          </Tooltip>
        </Space>
      </div>
      <ul className="breed-tree-root">
        <PalNode
          token={rootToken}
          palNameToId={palNameToId}
          palProfiles={palProfiles}
          pairByChild={pairByChild}
          isRoot
        />
      </ul>
    </div>
  );
}
