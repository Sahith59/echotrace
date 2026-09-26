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

it('lets an analyst inspect codec failures with class counts and unavailable metrics', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  const metrics = { recall: .874, false_positive_rate: .244, roc_auc: .906 }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    scope: 'Public data only.', serving_model: 'Baseline', experiments: [{
      name: 'Codec experiment', promoted: false, reason: 'False-positive gate failed.', sample_count: 2000,
      baseline: metrics, candidate: metrics,
      codec_slices: [{value:'C07', sample_count:100,
        baseline:{...metrics,genuine_count:60,synthetic_count:40},
        candidate:{recall:.8,false_positive_rate:.6,roc_auc:null,genuine_count:60,synthetic_count:40}}],
    }],
  }))))
  render(<ModelValidation />)
  await user.click(screen.getByText('Detector validation · measured performance'))
  const select = await screen.findByRole('combobox', {name:'Recording condition — Codec experiment'})
  await user.selectOptions(select, 'C07')
  expect(screen.getByText('60.0%')).toBeInTheDocument()
  expect(screen.getByText('60 genuine · 40 synthetic')).toBeInTheDocument()
  expect(screen.getByText('Not available')).toBeInTheDocument()
  expect(screen.getByText(/not an automatic label for this recording/)).toBeInTheDocument()
  await user.selectOptions(select, '__all__')
  expect(screen.queryByText('60.0%')).not.toBeInTheDocument()
  expect(screen.getAllByText('24.4%')).toHaveLength(2)
})
