import { type ReactNode, useMemo, useRef } from 'react'

import type { RenderSlotContribution } from '@/lib/render-slots'

import { ContribBoundary, ContribRender } from './boundary'
import { useContributions } from './use-contributions'

function renderOf<P>(data: unknown): RenderSlotContribution<P>['render'] | null {
  const render = (data as RenderSlotContribution<P> | undefined)?.render

  return typeof render === 'function' ? render : null
}

/** Number of contributions that can render in `area`. A host that wraps its own
 *  DOM for a slot (e.g. a bot row with children under it) only does so when this
 *  is non-zero, so an unused slot leaves the host's markup exactly as it was. */
export function useRenderSlotCount(area: string): number {
  const items = useContributions(area)

  return useMemo(() => items.filter(c => renderOf(c.data)).length, [items])
}

function RenderSlotEntry<P>({ id, props, render }: { id: string; props: P; render: (props: P) => ReactNode }) {
  // One component identity per registration: ContribRender mounts the callback AS
  // a component, so a closure over `props` would remount (and drop the plugin's
  // hook state) every time the host paints. The ref hands the current props to
  // that stable component, which re-renders with its parent.
  const latest = useRef(props)
  latest.current = props
  const mount = useMemo(() => () => render(latest.current), [render])

  return (
    <ContribBoundary id={id} variant="chip">
      <ContribRender render={mount} />
    </ContribBoundary>
  )
}

/** Mount every `data.render(props)` registered for `area`, in registry order.
 *  Renders nothing when the area has no registrations. */
export function RenderSlot<P>({ area, props }: { area: string; props: P }) {
  const items = useContributions(area)

  return (
    <>
      {items.map(c => {
        const render = renderOf<P>(c.data)

        return render ? (
          <RenderSlotEntry id={c.id} key={`${c.source ?? 'core'}:${c.id}`} props={props} render={render} />
        ) : null
      })}
    </>
  )
}
