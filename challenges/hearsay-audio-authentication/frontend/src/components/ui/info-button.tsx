import { useId, useState, type ReactNode } from 'react'
import { Info } from 'lucide-react'
export function InfoButton({label, children}: {label: string; children: ReactNode}) {
 const [open,setOpen]=useState(false);const id=useId()
 return <span className="info-control" onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();setOpen(false)}}} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))setOpen(false)}}>
  <button type="button" className="info-button" aria-label={`About ${label}`} aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}><Info size={16}/></button>
  {open && <span className="info-popover" id={id} role="note"><strong>{label}</strong>{children}</span>}
 </span>
}
