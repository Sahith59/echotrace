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
      baseline_model: 'Frozen wav2vec2', candidate_model: 'Adapted wav2vec2', name: 'Codec experiment', promoted: false, reason: 'False-positive gate failed.', sample_count: 2000,
      baseline: metrics, candidate: metrics,
      codec_slices: [{value:'C07', sample_count:100,
        baseline:{...metrics,genuine_count:60,synthetic_count:40},
        candidate:{recall:.8,false_positive_rate:.6,roc_auc:null,genuine_count:60,synthetic_count:40}}],
    }],
  }))))
  render(<ModelValidation />)
  await user.click(screen.getByText('How well has the detector worked on other recordings?'))
  await user.click(await screen.findByText('Earlier model experiments (1)'))
  await user.click(screen.getByText('Codec experiment'))
  const select = await screen.findByRole('combobox', {name:'Recording condition — Codec experiment'})
  expect(screen.getByText(/Baseline: Frozen wav2vec2/)).toBeInTheDocument()
  await user.selectOptions(select, 'C07')
  expect(screen.getByText('60.0%')).toBeInTheDocument()
  expect(screen.getByText('60 genuine · 40 synthetic')).toBeInTheDocument()
  expect(screen.getByText('Not available')).toBeInTheDocument()
  expect(screen.getByText(/not an automatic label for this recording/)).toBeInTheDocument()
  await user.selectOptions(select, '__all__')
  expect(screen.queryByText('60.0%')).not.toBeInTheDocument()
  expect(screen.getAllByText('24.4%')).toHaveLength(2)
})

it('shows the serving benchmark separately without inventing a baseline comparison', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    scope: 'Public benchmark replication.', serving_model: 'NII wav2vec anti-deepfake', experiments: [],
    serving_benchmarks: [{name:'Frozen In-the-Wild replication', model:'NII wav2vec anti-deepfake', sample_count:2000,
      genuine_count:1000,synthetic_count:1000,threshold:.5,recall:.937,false_positive_rate:.024,roc_auc:.9925,
      reason:'Prototype serving selection; not sponsor validation.'}],
  }))))
  render(<ModelValidation />)
  expect(await screen.findByText('Frozen In-the-Wild replication')).toBeInTheDocument()
  expect(screen.getByText('93.7%')).toBeInTheDocument()
  expect(screen.getByText('2.4%')).toBeInTheDocument()
  expect(screen.getByText('0.993')).toBeInTheDocument()
  expect(screen.getByText(/1,000 genuine · 1,000 synthetic/)).toBeInTheDocument()
  expect(screen.queryByText('Baseline')).not.toBeInTheDocument()
})

it('surfaces a failed new-domain quality check and out-of-scope clips', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    scope: 'Public benchmarks, not sponsor data.', serving_model: 'NII', experiments: [],
    serving_benchmarks: [{name:'ArA-DF-2026 stress check', model:'NII', status:'failed_quality_goal',
      sample_count:200, model_scored_count:198, genuine_count:100, synthetic_count:98,
      threshold:.5, recall:60/98, false_positive_rate:.07, roc_auc:.9018,
      reason:'Fixed single-shard sample; no serving change.'}],
  }))))
  render(<ModelValidation />)
  expect(await screen.findByText('ArA-DF-2026 stress check')).toBeInTheDocument()
  expect(screen.getByText('Goal missed here.')).toBeInTheDocument()
  expect(screen.getByText('This tests the model, not your current recording.')).toBeInTheDocument()
  expect(screen.getByText('38')).toBeInTheDocument()
  await user.click(screen.getByText('See test numbers and method'))
  expect(screen.getByText(/198 scored · 2 outside/)).toBeInTheDocument()
  expect(screen.getByText('61.2%')).toBeInTheDocument()
  expect(screen.getByText('7.0%')).toBeInTheDocument()
})
