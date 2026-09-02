import { type AnchorHTMLAttributes, type ReactNode, useId, useState } from "react";
import { classNames } from "../../utils/classNames.js";

export type NavLinkItem = {
  id: string;
  label: string;
  href: string;
  icon?: ReactNode;
  active?: boolean;
  /** Conteggio da evidenziare (EP13-P07); `0` o assente nasconde il badge. */
  badgeCount?: number;
  /** Etichetta accessibile del badge, fornita dall'app. */
  badgeLabel?: string;
  /** When true the item is omitted from assistive nav (handled by parent filter). */
  hidden?: boolean;
};

/** Collapsible section grouping related destinations (EP13-P01). */
export type NavGroupItem = {
  id: string;
  label: string;
  /** Item ids belonging to this group, in display order. */
  itemIds: readonly string[];
};

export type SidebarNavProps = {
  items: readonly NavLinkItem[];
  /** Optional groups; when omitted the nav renders a flat list as before. */
  groups?: readonly NavGroupItem[];
  /** Controlled open state. When omitted the component keeps its own state. */
  expandedGroupIds?: readonly string[];
  onToggleGroup?: (groupId: string) => void;
  ariaLabel?: string;
  className?: string;
  /** Render as anchor (default) or delegate navigation to app router. */
  linkComponent?: (props: NavLinkAnchorProps) => ReactNode;
};

export type NavLinkAnchorProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  active?: boolean;
};

function DefaultNavLink({ active, className, ...rest }: NavLinkAnchorProps) {
  return (
    <a
      className={classNames("fa-sidebar-nav__link", active && "fa-sidebar-nav__link--active", className)}
      aria-current={active ? "page" : undefined}
      {...rest}
    />
  );
}

type RenderNode =
  | { kind: "item"; item: NavLinkItem }
  | { kind: "group"; group: NavGroupItem; items: NavLinkItem[] };

/**
 * Places each visible item either standalone or inside its group. A group takes
 * the position of its first visible member, so standalone destinations keep
 * their relative order.
 */
function buildNodes(
  items: readonly NavLinkItem[],
  groups: readonly NavGroupItem[],
): RenderNode[] {
  const groupByItemId = new Map<string, NavGroupItem>();
  for (const group of groups) {
    for (const itemId of group.itemIds) {
      groupByItemId.set(itemId, group);
    }
  }

  const nodes: RenderNode[] = [];
  const groupNodes = new Map<string, Extract<RenderNode, { kind: "group" }>>();

  for (const item of items) {
    const group = groupByItemId.get(item.id);
    if (!group) {
      nodes.push({ kind: "item", item });
      continue;
    }
    let node = groupNodes.get(group.id);
    if (!node) {
      node = { kind: "group", group, items: [] };
      groupNodes.set(group.id, node);
      nodes.push(node);
    }
    node.items.push(item);
  }

  for (const node of groupNodes.values()) {
    node.items.sort(
      (a, b) => node.group.itemIds.indexOf(a.id) - node.group.itemIds.indexOf(b.id),
    );
  }

  return nodes;
}

export function SidebarNav({
  items,
  groups,
  expandedGroupIds,
  onToggleGroup,
  ariaLabel = "Navigazione principale",
  className,
  linkComponent: LinkComponent = DefaultNavLink,
}: SidebarNavProps) {
  const baseId = useId();
  const visibleItems = items.filter((item) => !item.hidden);
  const nodes = buildNodes(visibleItems, groups ?? []);

  // Uncontrolled fallback: groups start open so no destination is hidden by default.
  const [internalCollapsed, setInternalCollapsed] = useState<readonly string[]>([]);
  const isExpanded = (groupId: string) =>
    expandedGroupIds ? expandedGroupIds.includes(groupId) : !internalCollapsed.includes(groupId);

  function toggleGroup(groupId: string) {
    if (onToggleGroup) {
      onToggleGroup(groupId);
      return;
    }
    setInternalCollapsed((current) =>
      current.includes(groupId)
        ? current.filter((id) => id !== groupId)
        : [...current, groupId],
    );
  }

  function renderLink(item: NavLinkItem) {
    return (
      <LinkComponent href={item.href} active={item.active}>
        {item.icon ? (
          <span className="fa-sidebar-nav__icon" aria-hidden="true">
            {item.icon}
          </span>
        ) : null}
        <span className="fa-sidebar-nav__label">{item.label}</span>
        {item.badgeCount ? (
          <span
            className="fa-sidebar-nav__badge"
            data-testid={`sidebar-nav-badge-${item.id}`}
            aria-label={item.badgeLabel}
          >
            {item.badgeCount > 99 ? "99+" : item.badgeCount}
          </span>
        ) : null}
      </LinkComponent>
    );
  }

  return (
    <nav
      className={classNames("fa-sidebar-nav", className)}
      aria-label={ariaLabel}
      data-testid="sidebar-nav"
    >
      <ul className="fa-sidebar-nav__list">
        {nodes.map((node) => {
          if (node.kind === "item") {
            return (
              <li key={node.item.id} className="fa-sidebar-nav__item">
                {renderLink(node.item)}
              </li>
            );
          }

          const expanded = isExpanded(node.group.id);
          const containsActive = node.items.some((item) => item.active);
          const listId = `${baseId}-${node.group.id}`;

          return (
            <li key={node.group.id} className="fa-sidebar-nav__group">
              <button
                type="button"
                className={classNames(
                  "fa-sidebar-nav__group-toggle",
                  containsActive && "fa-sidebar-nav__group-toggle--active",
                )}
                aria-expanded={expanded}
                aria-controls={listId}
                onClick={() => toggleGroup(node.group.id)}
                data-testid={`sidebar-nav-group-${node.group.id}`}
              >
                <span className="fa-sidebar-nav__group-label">{node.group.label}</span>
                <span
                  className={classNames(
                    "fa-sidebar-nav__group-caret",
                    expanded && "fa-sidebar-nav__group-caret--expanded",
                  )}
                  aria-hidden="true"
                />
              </button>
              <ul id={listId} className="fa-sidebar-nav__group-list" hidden={!expanded}>
                {node.items.map((item) => (
                  <li key={item.id} className="fa-sidebar-nav__item">
                    {renderLink(item)}
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
