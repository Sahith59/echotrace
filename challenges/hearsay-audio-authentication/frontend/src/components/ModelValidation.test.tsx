import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import ModelValidation from './ModelValidation'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('shows independent metrics without describing an unpromoted experiment as the live model', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ scope: 'Public subset, not sponsor data.', serving_model: 'Baseline AASIST-L', experiments: [{name:'Experiment 01', promoted:false, reason:'Recall below target.',sample_count:2000,baseline:{recall:.225,false_positive_rate:.043,roc_auc:.698},candidate:{recall:.445,false_positive_rate:.040,roc_auc:.845}}] }))))
  render(<ModelValidation />)
  expect(await screen.findByText('44.5%')).toBeInTheDocument()
  expect(screen.getByText(/Experimental · not serving/)).toBeInTheDocument()
  expect(screen.getByText('Recall below target.')).toBeInTheDocument()
})
