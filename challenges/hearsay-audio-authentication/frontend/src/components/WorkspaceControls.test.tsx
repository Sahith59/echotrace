import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InfoButton } from './ui/info-button'
import { GlassCalendar } from './ui/glass-calendar'
afterEach(cleanup)
it('opens contextual help by keyboard and closes on Escape with focus retained', async () => {
 render(<InfoButton label="Synthesis score">A score is not identity proof.</InfoButton>)
 const user=userEvent.setup();await user.tab();await user.keyboard('{Enter}')
 expect(screen.getByRole('note')).toHaveTextContent('A score is not identity proof.')
 await user.keyboard('{Escape}')
 expect(screen.queryByRole('note')).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'About Synthesis score'})).toHaveFocus()
})
it('filters a real date, follows controlled selection and clears it', async () => {
 const select=vi.fn();const view=render(<GlassCalendar selectedDate="2026-09-26" onDateSelect={select} />)
 const user=userEvent.setup();await user.click(screen.getByRole('button',{name:'September 27, 2026'}))
 expect(select).toHaveBeenCalledWith('2026-09-27')
 view.rerender(<GlassCalendar selectedDate="2026-10-02" onDateSelect={select} />)
 expect(screen.getByRole('button',{name:'October 2, 2026'})).toHaveAttribute('aria-pressed','true')
 await user.click(screen.getByRole('button',{name:'Clear date filter'}));expect(select).toHaveBeenLastCalledWith(null)
})
