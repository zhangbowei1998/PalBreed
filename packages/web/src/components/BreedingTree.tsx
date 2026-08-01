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
}: {
  token: string;
  palNameToId: Record<string, string>;
  palProfiles: Record<string, PalProfile>;
  pairByChild: Map<string, SelectedPair>;
  isRoot?: boolean;
}) {
  const profile = resolveProfile(token, palNameToId, palProfiles);
  const displayName = profile?.cn_name ?? token;
  const pair = pairByChild.get(token);

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
          <PalNode
            token={pair.parent_a_id}
            palNameToId={palNameToId}
            palProfiles={palProfiles}
            pairByChild={pairByChild}
          />
          <PalNode
            token={pair.parent_b_id}
            palNameToId={palNameToId}
            palProfiles={palProfiles}
            pairByChild={pairByChild}
          />
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

  const visit = (childToken: string, indent: number) => {
    const pair = pairByChild.get(childToken);
    const childName = resolveName(childToken);
    if (!pair) {
      lines.push(`${"  ".repeat(indent)}${childName}`);
      return;
    }
    const a = resolveName(pair.parent_a_id);
    const b = resolveName(pair.parent_b_id);
    const prefix = indent === 0 ? "" : `${"  ".repeat(indent)}└─ `;
    lines.push(`${prefix}${childName} = ${a} + ${b}`);
    visit(pair.parent_a_id, indent + 1);
    visit(pair.parent_b_id, indent + 1);
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
    } catch {
      message.error("复制失败，请手动选择文本");
    }
  }

  /** 把 CDN 头像换成同源代理返回的 dataURL，供 html-to-image 无 CORS 渲染。 */
  async function embedImages(node: HTMLElement): Promise<() => void> {
    const imgs = Array.from(node.querySelectorAll<HTMLImageElement>("img"));
    const tasks = imgs
      .filter((img) => (img.getAttribute("src") ?? "").includes("cdn.paldb.cc"))
      .map(async (img) => {
        const src = img.getAttribute("src") ?? "";
        const match = src.match(/\/T_([^/]+?)_icon_normal\.webp$/);
        if (!match) return;
        try {
          const res = await fetch(`/agent/pal-image/${match[1]}`);
          if (!res.ok) return;
          const blob = await res.blob();
          const dataUrl = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result));
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
          const original = src;
          img.setAttribute("src", dataUrl);
          img.setAttribute("data-original-src", original);
        } catch {
          // 保持原样
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
