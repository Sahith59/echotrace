import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
export function localDate(date:Date) { return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}` }
/** Adapted from the supplied glass-calendar: controlled date filtering, no decorative dead actions. */
export function GlassCalendar({selectedDate,onDateSelect}: {selectedDate:string|null;onDateSelect:(value:string|null)=>void}) {
 const [month,setMonth]=useState(()=>selectedDate?new Date(`${selectedDate}T12:00:00`):new Date())
 const reduced=useReducedMotion()
 useEffect(()=>{if(selectedDate)setMonth(new Date(`${selectedDate}T12:00:00`))},[selectedDate])
 const label=month.toLocaleDateString('en-US',{month:'long',year:'numeric'})
 const first=new Date(month.getFullYear(),month.getMonth(),1).getDay()
 const count=new Date(month.getFullYear(),month.getMonth()+1,0).getDate()
 return <section className="glass-calendar" aria-label="Filter recordings by date">
  <div className="calendar-caption"><CalendarDays size={15}/><span>Date added · local time</span></div>
  <div className="calendar-heading"><motion.h3 key={label} initial={{opacity:reduced?1:0}} animate={{opacity:1}} transition={{duration:.15}}>{label}</motion.h3><div><button aria-label="Previous month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}><ChevronLeft size={16}/></button><button aria-label="Next month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}><ChevronRight size={16}/></button></div></div>
  <div className="calendar-days"><div className="calendar-week" aria-hidden="true">{'SMTWTFS'.split('').map((day,i)=><span key={i}>{day}</span>)}</div><div className="calendar-grid">
   {Array.from({length:first},(_,i)=><span key={`blank-${i}`}/>)}
   {Array.from({length:count},(_,i)=>{const date=new Date(month.getFullYear(),month.getMonth(),i+1);const value=localDate(date);return <button key={value} aria-label={date.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})} aria-pressed={selectedDate===value} aria-current={value===localDate(new Date())?'date':undefined} onClick={()=>onDateSelect(value)}>{i+1}</button>})}
  </div></div><button className="calendar-clear" onClick={()=>onDateSelect(null)}>Clear date filter</button>
 </section>
}
