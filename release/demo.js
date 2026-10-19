(() => {
  "use strict";
  // Preserve the deterministic invented race from the first public demo.
  const cars = [
    {id:"7",type:"HYPERCAR",base:222.7,phase:.2},
    {id:"51",type:"HYPERCAR",base:223.5,phase:1.1},
    {id:"8",type:"HYPERCAR",base:224.2,phase:2},
    {id:"85",type:"LMGT3",base:240.8,phase:.7},
    {id:"46",type:"LMGT3",base:242.3,phase:1.7},
    {id:"27",type:"LMGT3",base:243.1,phase:2.7}
  ];
  const laps = [];
  for (const car of cars) {
    let elapsed = car.type === "HYPERCAR" ? Number(car.id)*.14 : 9+Number(car.id)*.11;
    for (let lap=1; lap<=11; lap++) {
      const variation = 1.7*Math.sin(lap*1.39+car.phase)+.65*Math.cos(lap*.72+car.phase);
      const slow = car.type === "HYPERCAR" && ((car.id === "7" && lap === 7)||(car.id === "51" && lap === 9)) ? 4.8 : 0;
      const duration = Number((car.base+variation+slow).toFixed(2));
      elapsed = Number((elapsed+duration).toFixed(2));
      laps.push({car:car.id,type:car.type,lap,duration,elapsed,event:slow>0 ? "Scripted delay" : ""});
    }
  }
  laps.sort((a,b)=>a.elapsed-b.elapsed||a.car.localeCompare(b.car));
  const $ = id => document.getElementById(id);
  const median = values => {
    const sorted=[...values].sort((a,b)=>a-b),n=sorted.length;
    return n%2 ? sorted[(n-1)/2] : (sorted[n/2-1]+sorted[n/2])/2;
  };
  const seconds = value => `${value.toFixed(2)} s`;
  const elapsedTime = value => {
    const tenths=Math.round(value*10),minutes=Math.floor(tenths/600);
    return `${String(minutes).padStart(2,"0")}:${((tenths%600)/10).toFixed(1).padStart(4,"0")}`;
  };
  let revealed=false;
  const carSelect=$("car"),lapSelect=$("lap");

  function snapshot() {
    const id=carSelect.value,lap=Number(lapSelect.value);
    const history=laps.filter(row=>row.car===id).sort((a,b)=>a.lap-b.lap);
    const origin=history.find(row=>row.lap===lap),target=history.find(row=>row.lap===lap+1);
    if (!origin||!target) throw new Error("Invalid forecast origin");
    const available=laps.filter(row=>row.elapsed<=origin.elapsed),state=new Map();
    for (const row of available) state.set(row.car,row);
    const known=[...state.values()].sort((a,b)=>a.type.localeCompare(b.type)||Number(a.car)-Number(b.car));
    const prior=history.filter(row=>row.lap<=lap),clean=prior.filter(row=>!row.event).slice(-3);
    const baseline=Number(median(clean.map(row=>row.duration)).toFixed(2));
    const crossings=available.filter(row=>row.type==="LMGT3"&&origin.elapsed-row.elapsed<=30).length;
    console.assert(known.every(row=>row.elapsed<=origin.elapsed),"Future crossing in the known field");
    console.assert(clean.every(row=>row.lap<=lap&&!row.event),"Invalid baseline input");
    console.assert(known.length===state.size&&cars.length===6&&laps.length===66,"Race totals disagree");
    return {id,lap,history,origin,target,known,prior,clean,baseline,crossings};
  }
  function element(tag,className,text) {
    const node=document.createElement(tag);
    if(className) node.className=className;
    if(text!==undefined) node.textContent=text;
    return node;
  }
  function render() {
    const view=snapshot();
    $("origin-time").textContent=elapsedTime(view.origin.elapsed);
    $("target-label").textContent=`Predicting lap ${view.target.lap}`;
    $("baseline").textContent=view.baseline.toFixed(2);
    $("estimate-note").textContent=`Median of ${view.clean.length} clean completed laps.`;
    $("history-range").textContent=`Car #${view.id} · laps 1–${view.lap}`;
    $("field-summary").textContent=`${view.known.length} cars observed by ${elapsedTime(view.origin.elapsed)}`;
    $("field-note").textContent=`${view.crossings} LMGT3 ${view.crossings===1?"crossing":"crossings"} in the preceding 30 seconds. Crossing proximity alone does not establish an on-track encounter.`;
    $("previous").disabled=view.lap<=2; $("next").disabled=view.lap>=10;
    $("previous").title=view.lap<=2?"Lap 2 is the first available origin":"Previous lap";
    $("next").title=view.lap>=10?"Lap 10 is the final available origin":"Next lap";
    $("pace-inputs").replaceChildren(...view.clean.map(row=>{
      const input=element("div","pace-input");
      input.append(element("span","",`Lap ${row.lap}`),element("b","",seconds(row.duration)));
      return input;
    }));
    renderTimeline(view); renderField(view); renderChart(view); renderOutcome(view);
    $("replay-status").textContent=`Car ${view.id}, lap ${view.lap} complete. Forecast for lap ${view.target.lap}: ${seconds(view.baseline)}. Cutoff ${elapsedTime(view.origin.elapsed)}.`;
  }
  function renderTimeline(view) {
    $("timeline").replaceChildren(...view.history.slice(0,10).map(row=>{
      const button=element("button",`lap-button${row.lap>view.lap?" future":""}`);
      button.type="button"; button.disabled=row.lap<2;
      button.setAttribute("aria-pressed",String(row.lap===view.lap));
      button.setAttribute("aria-label",row.lap<2?"Lap 1, insufficient history for a forecast origin":`Choose completed lap ${row.lap}`);
      const inner=element("span","lap-inner");
      const lapLabel=element("span","lap-number",`Lap ${row.lap}`);
      if(row.lap===view.lap) lapLabel.append(element("span","current-marker"," · now"));
      inner.append(lapLabel);
      inner.append(element("span","lap-duration",row.lap<=view.lap?seconds(row.duration):"Hidden"));
      button.append(inner);
      button.addEventListener("click",()=>{lapSelect.value=row.lap;moveOrigin()});
      return button;
    }));
  }
  function renderField(view) {
    $("state").replaceChildren(...view.known.map(row=>{
      const tr=element("tr",`state-row${row.car===view.id?" selected-car":""}`);
      tr.dataset.car=row.car;
      const identity=element("td",""),name=element("span","car-identity");
      name.innerHTML='<svg class="car-silhouette" viewBox="0 0 38 18" aria-hidden="true"><path d="m2 12 4-1 5-6h11l7 6 6 1v3H2zM9 15h5m12 0h5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="m12 7-3 4h15l-4-4z" fill="currentColor"/></svg>';
      name.append(element("span","car-number",`#${row.car}`));
      if(row.car===view.id) name.append(element("span","selected-note","Selected"));
      identity.append(name);
      tr.append(identity,element("td","",row.type==="HYPERCAR"?"Hypercar":"LMGT3"));
      for(const [value,label] of [[row.lap,"Lap "],[seconds(row.duration),""],[elapsedTime(row.elapsed),"At "],[`${(view.origin.elapsed-row.elapsed).toFixed(1)} s`,"Age "]]) {
        const td=element("td","numeric");
        if(label) td.append(element("span","mobile-label",label));
        td.append(document.createTextNode(String(value))); tr.append(td);
      }
      return tr;
    }));
  }
  function renderOutcome(view) {
    $("outcome").hidden=!revealed;
    $("reveal").setAttribute("aria-expanded",String(revealed));
    $("reveal").textContent=revealed?"Hide outcome":"Reveal next lap";
    $("reveal-note").textContent=revealed?`Lap ${view.target.lap} outcome shown`:"Hidden at this crossing";
    $("actual").textContent=revealed?seconds(view.target.duration):"—";
    $("error").textContent=revealed?seconds(Math.abs(view.baseline-view.target.duration)):"—";
    $("outcome-note").textContent=revealed?(view.target.event?"This next lap includes a scripted delay.":"This next lap has no scripted delay."):"";
  }
  function renderChart(view) {
    const root=$("chart"),ns="http://www.w3.org/2000/svg";
    const width=Math.max(270,root.clientWidth),height=root.clientHeight;
    const left=42,right=width-14,top=23,bottom=height-30;
    // Never let the hidden next-lap outcome determine the visible chart scale.
    const values=[...view.prior.map(row=>row.duration),view.baseline];
    const min=Math.floor((Math.min(...values)-1)/2)*2,max=Math.ceil((Math.max(...values)+1)/2)*2;
    const step=Math.max(2,Math.ceil((max-min)/8)*2),ceiling=min+Math.ceil((max-min)/step)*step;
    const x=lap=>left+(lap-1)/view.lap*(right-left);
    const y=seconds=>bottom-(seconds-min)/(ceiling-min)*(bottom-top);
    const svg=document.createElementNS(ns,"svg");
    svg.setAttribute("viewBox",`0 0 ${width} ${height}`);svg.setAttribute("aria-hidden","true");
    const add=(tag,attrs,text)=>{
      const node=document.createElementNS(ns,tag);
      for(const [key,value] of Object.entries(attrs)) node.setAttribute(key,value);
      if(text!==undefined) node.textContent=text;
      svg.append(node);return node;
    };
    const tokens=getComputedStyle(document.documentElement);
    const muted=tokens.getPropertyValue("--muted").trim(),grid=tokens.getPropertyValue("--grid").trim(),accent=tokens.getPropertyValue("--accent").trim();
    for(let tick=min;tick<=ceiling;tick+=step) {
      add("line",{x1:left,x2:right,y1:y(tick),y2:y(tick),stroke:grid,"stroke-width":1});
      add("text",{x:left-10,y:y(tick)+4,fill:muted,"font-size":11,"text-anchor":"end"},tick);
    }
    const textStyle={fill:muted,"font-size":11};
    add("text",{x:left-10,y:11,"text-anchor":"end",...textStyle},"s");
    const xStep=width<400?Math.max(1,Math.ceil(view.lap/3)):Math.max(1,Math.ceil(view.lap/5));
    for(let lap=1;lap<=view.lap+1;lap+=xStep) add("text",{x:x(lap),y:height-9,"text-anchor":"middle",...textStyle},lap);
    add("text",{x:right,y:11,"text-anchor":"end",...textStyle},"Lap");
    add("line",{x1:left,x2:right,y1:y(view.baseline),y2:y(view.baseline),stroke:muted,"stroke-dasharray":"4 4","stroke-width":1});
    add("polyline",{points:view.prior.map(row=>`${x(row.lap)},${y(row.duration)}`).join(" "),fill:"none",stroke:accent,"stroke-width":1.5,"stroke-linejoin":"round"});
    add("line",{x1:x(view.lap),x2:x(view.lap),y1:top,y2:bottom,stroke:grid,"stroke-width":1});
    const last=view.prior[view.prior.length-1];
    add("circle",{cx:x(last.lap),cy:y(last.duration),r:3,fill:accent});
    const delay=view.prior.find(row=>row.event);
    if(delay) add("text",{x:Math.min(right-3,Math.max(left+65,x(delay.lap))),y:Math.max(18,y(delay.duration)-10),"text-anchor":"end",...textStyle},"Scripted delay");
    root.setAttribute("aria-label",`Car ${view.id}, completed laps 1 to ${view.lap}. ${view.prior.map(row=>`Lap ${row.lap}: ${seconds(row.duration)}`).join(". ")}. Pace estimate: ${seconds(view.baseline)}. Vertical scale ${min} to ${ceiling} seconds.`);
    root.replaceChildren(svg);
  }
  function moveOrigin(){revealed=false;render()}
  $("retry").addEventListener("click",()=>location.reload());
  try {
    render();
    carSelect.addEventListener("change",moveOrigin);lapSelect.addEventListener("change",moveOrigin);
    $("previous").addEventListener("click",()=>{lapSelect.value=Math.max(2,Number(lapSelect.value)-1);moveOrigin()});
    $("next").addEventListener("click",()=>{lapSelect.value=Math.min(10,Number(lapSelect.value)+1);moveOrigin()});
    $("reveal").addEventListener("click",()=>{revealed=!revealed;renderOutcome(snapshot())});
    let resizeFrame;
    window.addEventListener("resize",()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>renderChart(snapshot()))});
    document.fonts.ready.then(()=>renderChart(snapshot()));
  } catch(error) {$("error-message").hidden=false;console.error(error)}
})();
