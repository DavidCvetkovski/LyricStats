"use client";
import { useEffect, useRef, useState, type ReactNode } from 'react';
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
 const ref=useRef<T>(null);const [visible,setVisible]=useState(false);
 useEffect(()=>{const el=ref.current;if(!el)return;const observer=new IntersectionObserver(([e])=>{if(e.isIntersecting){setVisible(true);observer.disconnect();}},{threshold:0.12});observer.observe(el);return()=>observer.disconnect();},[]);
 return {ref,visible};
}
export function Reveal({children,className=''}:{children:ReactNode;className?:string}) {
 const {ref,visible}=useReveal();return <div ref={ref} className={`editorial-reveal ${visible?'is-visible':''} ${className}`}>{children}</div>;
}
export function Count({value,suffix='',decimals=0}:{value:number;suffix?:string;decimals?:number}) {
 const {ref,visible}=useReveal<HTMLSpanElement>();const [n,setN]=useState(value);
 useEffect(()=>{if(!visible)return;const motion=window.matchMedia('(prefers-reduced-motion: reduce)');if(motion.matches){setN(value);return;}let id=0;const start=performance.now();const tick=(now:number)=>{const p=Math.min(1,(now-start)/1100);setN(value*(1-(1-p)**3));if(p<1)id=requestAnimationFrame(tick);};id=requestAnimationFrame(tick);return()=>cancelAnimationFrame(id);},[visible,value]);
 return <span ref={ref} aria-label={`${value.toFixed(decimals)}${suffix}`}><span aria-hidden>{n.toLocaleString(undefined,{minimumFractionDigits:decimals,maximumFractionDigits:decimals})}{suffix}</span></span>;
}
