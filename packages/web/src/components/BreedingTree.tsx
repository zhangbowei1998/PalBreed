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

export function BreedingTree({ targetPal, selectedPairs, palNameToId, palProfiles }: Props) {
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

  return (
    <div className="breed-tree">
      <h3 className="breed-tree-title">已确认配种路径</h3>
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
