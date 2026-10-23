import { act, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { registry } from '@/contrib/registry'

import { RenderSlot, useRenderSlotCount } from './render-slot'

const AREA = 'test.render-slot'
const disposers: Array<() => void> = []

function add(id: string, render: unknown) {
  disposers.push(registry.register({ area: AREA, data: { render }, id } as never))
}

afterEach(() => {
  while (disposers.length) {
    disposers.pop()?.()
  }
})

function Count() {
  return <output data-testid="count">{useRenderSlotCount(AREA)}</output>
}

describe('RenderSlot (render-slot seam)', () => {
  it('renders nothing and counts zero when the area is empty', () => {
    const { container } = render(
      <>
        <RenderSlot area={AREA} props={{ name: 'infra' }} />
        <Count />
      </>
    )

    expect(screen.getByTestId('count').textContent).toBe('0')
    expect(container.querySelectorAll('[data-testid="slot-child"]').length).toBe(0)
  })

  it('mounts every registration with the host props; null declines', () => {
    add('a', (p: { name: string }) => <span data-testid="slot-child">A:{p.name}</span>)
    add('b', (p: { name: string }) => (p.name === 'infra' ? null : <span data-testid="slot-child">B</span>))
    add('not-a-render', 'nope')
    render(
      <>
        <RenderSlot area={AREA} props={{ name: 'infra' }} />
        <Count />
      </>
    )

    expect(screen.getAllByTestId('slot-child').map(n => n.textContent)).toEqual(['A:infra'])
    expect(screen.getByTestId('count').textContent).toBe('2')
  })

  it('keeps plugin hook state across host repaints (stable component identity)', () => {
    let mounts = 0

    function Child({ name }: { name: string }) {
      const [id] = useState(() => ++mounts)

      return <span data-testid="slot-child">{`${name}:${id}`}</span>
    }

    add('stateful', (p: { name: string }) => <Child name={p.name} />)
    const Host = ({ name }: { name: string }) => <RenderSlot area={AREA} props={{ name }} />
    const { rerender } = render(<Host name="infra" />)
    rerender(<Host name="field" />)
    rerender(<Host name="parts" />)
    expect(screen.getByTestId('slot-child').textContent).toBe('parts:1')
    expect(mounts).toBe(1)
  })

  it('isolates a throwing contribution in its own boundary', () => {
    add('boom', () => {
      throw new Error('plugin bug')
    })
    add('ok', () => <span data-testid="slot-child">still here</span>)
    const spy = console.error
    console.error = () => undefined

    try {
      render(<RenderSlot area={AREA} props={{}} />)
    } finally {
      console.error = spy
    }

    expect(screen.getByTestId('slot-child').textContent).toBe('still here')
  })

  it('follows live registration and disposal', () => {
    render(<RenderSlot area={AREA} props={{}} />)
    expect(screen.queryByTestId('slot-child')).toBeNull()
    act(() => add('late', () => <span data-testid="slot-child">late</span>))
    expect(screen.getByTestId('slot-child').textContent).toBe('late')
    act(() => disposers.pop()?.())
    expect(screen.queryByTestId('slot-child')).toBeNull()
  })
})
