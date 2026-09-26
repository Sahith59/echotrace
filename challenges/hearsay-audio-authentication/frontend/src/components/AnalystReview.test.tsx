import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AnalystReview from './AnalystReview'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status})
it('saves analyst judgment separately with its loaded version',async()=>{
 const fetcher=vi.fn((_url:string,init?:RequestInit)=>Promise.resolve(response(init?.method==='PUT'?{status:'review_complete',notes:'Call back via trusted number.',version:1}:{status:'needs_review',notes:'',version:0})))
 vi.stubGlobal('fetch',fetcher);const saved=vi.fn();render(<AnalystReview jobId="case1" onSaved={saved}/>);const user=userEvent.setup()
 await user.selectOptions(await screen.findByLabelText('Review status'),'review_complete')
 await user.type(screen.getByLabelText('Analyst notes'),'Call back via trusted number.')
 await user.click(screen.getByRole('button',{name:'Save review'}))
 expect(await screen.findByText('Review saved.')).toBeInTheDocument()
 const init=fetcher.mock.calls.find(([,init])=>init?.method==='PUT')?.[1];expect(JSON.parse(init?.body as string)).toEqual({status:'review_complete',notes:'Call back via trusted number.',expected_version:0});expect(saved).toHaveBeenCalled()
})
it('preserves a draft when another analyst has changed the saved version',async()=>{
 vi.stubGlobal('fetch',vi.fn((_url:string,init?:RequestInit)=>Promise.resolve(init?.method==='PUT'?response({detail:'Review changed. Reload before saving.'},409):response({status:'needs_review',notes:'',version:0}))))
 render(<AnalystReview jobId="case1" onSaved={()=>{}}/>);const user=userEvent.setup()
 await user.type(await screen.findByLabelText('Analyst notes'),'Keep my draft')
 await user.click(screen.getByRole('button',{name:'Save review'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('Review changed')
 expect(screen.getByLabelText('Analyst notes')).toHaveValue('Keep my draft')
 expect(screen.queryByText('Review saved.')).not.toBeInTheDocument()
})
