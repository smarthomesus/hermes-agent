import type { ReactNode } from 'react'

/**
 * RENDER SLOTS — host-owned mount points that hand a contribution the props of
 * the surface it renders in.
 *
 * `statusBar.*` / `titleBar.*` / `panes` give a plugin a place, never the thing
 * the user is looking at. Some extensions need exactly that thing: a line under
 * ONE bot in the sidebar, an overlay over ONE chat. A generic pane is not the
 * same feature, so these areas mount every registration INSIDE the surface and
 * pass that surface's identity as props. Same contract as `chat.empty`:
 *
 *   ctx.register({ id, area: BOT_ROW_AREAS.after, data: { render: props => ... } })
 *
 * `render` returns an element, or `null` to decline (e.g. a bot it does not
 * own). Every registration is mounted and answers for itself, each inside its
 * own contribution error boundary, so a throwing plugin degrades to an inline
 * error in its slot and the bot row / chat keep working. With no registrations
 * a slot renders nothing and the host DOM is unchanged.
 *
 * Props are read-only views. They carry no request function and no authority:
 * a plugin that needs data talks to its own backend (`ctx.rest`) or the
 * gateway (`host.request*`), where the server-side ACL decides.
 */

/** Areas rendered inside each Bots-sidebar row (hermes-bots BotRow). */
export const BOT_ROW_AREAS = {
  /** Inline, right after the bot's display name (status chips: "Working"). */
  nameSuffix: 'bots.row.nameSuffix',
  /** Its own line under the name row (badges such as open-task counts). */
  meta: 'bots.row.meta',
  /** Below the whole row (expandable children, e.g. a desk's sub-workers). */
  after: 'bots.row.after'
} as const

/** Overlay mounted inside the chat transcript bounds of every chat view. */
export const CHAT_OVERLAY_AREA = 'chat.overlay'

/** Section mounted at the top of the Agents (sub-agents) panel. */
export const AGENTS_PANEL_AREA = 'agents.panel.header'

/** Read-only identity of the bot row a `bots.row.*` contribution renders in. */
export interface BotRowSlotProps {
  /** Profile name the row stands for (`default` = the launch profile). */
  name: string
  /** Connection the row was listed from (`local` for this machine). */
  connectionId: string
  /** The roster row as the sidebar received it (treat as immutable). */
  bot: Readonly<Record<string, unknown>>
}

/** Read-only identity of the chat a `chat.overlay` contribution renders over. */
export interface ChatOverlaySlotProps {
  /** Stored (database) session id of the open chat, if any. */
  storedId: string | null
  /** Live runtime session id of the open chat, if any. */
  runtimeId: string | null
  /** Profile the chat belongs to (`default` = the launch profile). */
  profile: string
}

/** The agents panel passes nothing; a section reads its own data. */
export type AgentsPanelSlotProps = Record<string, never>

/** Payload of a render-slot contribution's `data`. */
export interface RenderSlotContribution<P> {
  render: (props: P) => ReactNode
}
