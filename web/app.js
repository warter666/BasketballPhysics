const canvas=document.getElementById("game"),ctx=canvas.getContext("2d");
const W=1280,H=720,GROUND=625,G=980,BALL_R=15,MAX_DRAG=300,MAX_ATTEMPTS=5,ADVANCE_DELAY=1200;
const START={x:145,y:GROUND-BALL_R};
const ui={
 level:document.getElementById("level"),hp:document.getElementById("hp"),runStatus:document.getElementById("runStatus"),runMap:document.getElementById("runMap"),attempts:document.getElementById("attempts"),made:document.getElementById("made"),
 angle:document.getElementById("angle"),power:document.getElementById("power"),spin:document.getElementById("spin"),
 result:document.getElementById("result"),detail:document.getElementById("detail"),tip:document.getElementById("tip"),
 levelTag:document.getElementById("levelTag"),levelName:document.getElementById("levelName"),levelGoal:document.getElementById("levelGoal"),
 goalText:document.getElementById("goalText"),attemptMeter:document.getElementById("attemptMeter"),attemptText:document.getElementById("attemptText"),
 distance:document.getElementById("labDistance"),apex:document.getElementById("labApex"),collision:document.getElementById("labCollision"),
 outcome:document.getElementById("labOutcome"),diagnosis:document.getElementById("diagnosis"),
 buildSummary:document.getElementById("buildSummary"),buildList:document.getElementById("buildList"),
 rewardModal:document.getElementById("rewardModal"),rewardList:document.getElementById("rewardList")
};

const levels=[
 {name:"起点",goal:"学会控制基础角度与力量",tip:"先让球稳定地落入篮筐，不需要碰撞。",hoop:{x:1080,y:365},obs:[],kind:"normal"},
 {name:"弧高",goal:"从高处越过弧高杆",tip:"杆挡住低弧线：提高仰角，同时补足力量。",hoop:{x:1080,y:365},obs:[{t:"bar",x:575,y:320,w:34,h:305}],kind:"normal"},
 {name:"反弹",goal:"利用墙面改变球的方向",tip:"不要直接瞄准篮筐，先让墙成为轨迹的一部分。",hoop:{x:1080,y:365},obs:[{t:"wall",x:700,y:300,w:34,h:270}],kind:"normal"},
 {name:"通道",goal:"规划连续轨迹穿过通道",tip:"先决定球从哪个入口进入，再决定出手角度。",hoop:{x:1080,y:365},obs:[{t:"block",x:520,y:160,w:360,h:90},{t:"block",x:520,y:340,w:360,h:130},{t:"wall",x:880,y:0,w:34,h:250}],kind:"challenge"},
 {name:"时机",goal:"等待移动障碍打开路线",tip:"移动障碍是时间问题：角度正确还不够，要抓住窗口。",hoop:{x:1080,y:365},obs:[{t:"bar",x:640,y:350,w:34,h:145,move:true},{t:"wall",x:870,y:310,w:34,h:260}],kind:"challenge"},
 {name:"低弧反弹",goal:"低弧线进入，再用墙面修正",tip:"先压低弧线，撞墙后利用反弹角度进入篮筐。",hoop:{x:1110,y:380},obs:[{t:"wall",x:650,y:390,w:34,h:235},{t:"bar",x:500,y:250,w:34,h:220}],kind:"challenge"},
 {name:"双障碍",goal:"连续处理两个物理表面",tip:"这一关开始考验构筑：旋转和反弹能量都会改变路线。",hoop:{x:1100,y:340},obs:[{t:"wall",x:560,y:280,w:34,h:280},{t:"bar",x:790,y:170,w:34,h:300}],kind:"elite"},
 {name:"移动通道",goal:"在移动窗口中穿过通道",tip:"不要追求完美轨迹，找一个稳定的时间窗口。",hoop:{x:1110,y:350},obs:[{t:"block",x:520,y:130,w:380,h:95},{t:"block",x:520,y:390,w:380,h:105},{t:"bar",x:760,y:255,w:34,h:115,move:true}],kind:"elite"},
 {name:"最终考验",goal:"综合利用角度、碰撞与旋转",tip:"最后一关前的综合测试：没有单一正确投法。",hoop:{x:1130,y:330},obs:[{t:"wall",x:600,y:300,w:34,h:280},{t:"bar",x:760,y:150,w:34,h:300},{t:"bar",x:930,y:370,w:34,h:180,move:true}],kind:"elite"},
 {name:"DUEL BOSS",goal:"突破 Boss 防线并完成本局",tip:"Boss 会同时考验反弹、弧高和时机。构筑应该开始体现价值。",hoop:{x:1135,y:315},obs:[{t:"wall",x:560,y:260,w:34,h:320},{t:"bar",x:730,y:120,w:34,h:330},{t:"wall",x:900,y:300,w:34,h:280},{t:"bar",x:1030,y:170,w:34,h:220,move:true}],kind:"boss"}
];

let level=0,levelShots=0,totalShots=0,made=0,spin=0,hp=3,drag=null,ball=null,preview=[],lastShot=null,advanceTimer=null,runEnded=false,secondChanceUsed=false;
const build={spinMaster:0,bankShot:0,secondChance:0};
const REWARDS=[
 {id:"spinMaster",name:"旋转大师",desc:"反弹时旋转影响 ×1.8。主动利用旋转改变路线。",tag:"改变反弹方向"},
 {id:"bankShot",name:"银行球",desc:"篮板/支架碰撞损失降低。打板路线更容易保留速度。",tag:"改变碰撞能量"},
 {id:"secondChance",name:"二次机会",desc:"每关第一次触碰篮筐区域后，获得一次额外向上反弹容错。",tag:"改变容错方式"}
];
let levelStartedAt=performance.now(),lastTime=performance.now(),movingClock=0;

function current(){return levels[level]}
function ballStart(){return{x:START.x,y:START.y,vx:0,vy:0,active:false,t:0,path:[],collisions:0}}
function renderRunMap(){
 ui.runStatus.textContent="NODE "+(level+1)+" / "+levels.length+(levels[level].kind==="boss"?" · BOSS":"");
 ui.runMap.innerHTML=levels.map((l,i)=>{
   const state=i<level?"done":i===level?"current":"locked";
   return `<span class="run-node ${state} ${l.kind}" title="${l.name}">${i+1}</span>`;
 }).join('<i></i>');
 ui.hp.textContent=hp;
}
function renderBuild(){
 const names=REWARDS.filter(r=>build[r.id]>0).map(r=>r.name+" ×"+build[r.id]);
 ui.buildSummary.textContent=names.length?names.join(" · "):"基础投篮";
 ui.buildList.innerHTML=names.map(n=>`<span class="build-chip">${n}</span>`).join("");
}
function reset(){
 if(advanceTimer){clearTimeout(advanceTimer);advanceTimer=null}
 ball=null;drag=null;preview=[];lastShot=null;levelShots=0;levelStartedAt=performance.now();secondChanceUsed=false;
 ui.result.textContent="准备出手";ui.detail.textContent=current().tip;ui.tip.textContent="拖动篮球：方向 = 角度，距离 = 力量；滚轮 = 旋转";
 ui.level.textContent=level+1;renderRunMap();ui.levelTag.textContent="LEVEL "+(level+1);ui.levelName.textContent=current().name;ui.levelGoal.textContent=current().goal;
 ui.goalText.textContent=current().goal;updateAttemptUI();updateLab(null);renderBuild();draw();
}
function updateAttemptUI(){
 ui.attempts.textContent=levelShots;ui.attemptMeter.style.width=(levelShots/MAX_ATTEMPTS*100)+"%";
 ui.attemptText.textContent=levelShots<MAX_ATTEMPTS?("本关剩余 "+(MAX_ATTEMPTS-levelShots)+" 次尝试"):"本关尝试已用完";
}
function pointer(e){const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*W/r.width,y:(e.clientY-r.top)*H/r.height}}
function getAim(p){
 const b=ball||ballStart(),dx=b.x-p.x,dy=b.y-p.y,len=Math.min(MAX_DRAG,Math.hypot(dx,dy));
 return{dx,dy,len,angle:Math.atan2(-dy,dx),power:len/MAX_DRAG}
}
function velocity(a,p){const speed=380+Math.pow(p,0.72)*980;return{vx:Math.cos(a)*speed,vy:-Math.sin(a)*speed}}
function movingObstacle(o,t=movingClock){return{...o,y:o.y+Math.sin(t*1.43)*70}}
function obstacleSnapshot(t=movingClock){return current().obs.map(o=>o.move?movingObstacle(o,t):o)}
function circleRect(s,o){
 const cx=Math.max(o.x,Math.min(s.x,o.x+o.w)),cy=Math.max(o.y,Math.min(s.y,o.y+o.h));
 return(s.x-cx)**2+(s.y-cy)**2<BALL_R**2
}
function resolveRect(s,o){
 const left=Math.abs((s.x+BALL_R)-o.x),right=Math.abs((o.x+o.w)-(s.x-BALL_R));
 const top=Math.abs((s.y+BALL_R)-o.y),bottom=Math.abs((o.y+o.h)-(s.y-BALL_R)),m=Math.min(left,right,top,bottom);
 const restitution=Math.min(.96,.78+build.bankShot*.07);
 if(m===left){s.x=o.x-BALL_R;s.vx=-Math.abs(s.vx)*restitution}
 else if(m===right){s.x=o.x+o.w+BALL_R;s.vx=Math.abs(s.vx)*restitution}
 else if(m===top){s.y=o.y-BALL_R;s.vy=-Math.abs(s.vy)*restitution}
 else{s.y=o.y+o.h+BALL_R;s.vy=Math.abs(s.vy)*restitution}
 s.vx+=spin*18*(1+build.spinMaster*.8)
}
function boardRect(){const h=current().hoop;return{x:h.x+55,y:h.y-85,w:12,h:120}}
function hoopScore(s,prev){
 const h=current().hoop,crossed=prev.y<h.y&&s.y>=h.y&&s.vy>0&&s.x>h.x-34&&s.x<h.x+34;
 return crossed
}
function simulate(v,startTime=movingClock,steps=300){
 let s={x:START.x,y:START.y,vx:v.vx,vy:v.vy},path=[],hits=0,apex=s.y,rimTouched=false;
 for(let i=0;i<steps;i++){
   const t=startTime+i/60;s.vy+=G/60;s.x+=s.vx/60;s.y+=s.vy/60;apex=Math.min(apex,s.y);
   if(s.y+BALL_R>GROUND){s.y=GROUND-BALL_R;s.vy*=-.64;s.vx*=.93;hits++}
   if(s.x-BALL_R<0){s.x=BALL_R;s.vx=Math.abs(s.vx)*.72;hits++}
   for(const o of obstacleSnapshot(t)){if(circleRect(s,o)){resolveRect(s,o);hits++}}
   if(circleRect(s,boardRect())){resolveRect(s,boardRect());hits++;
     if(build.secondChance>0&&hits===1){s.vy=-Math.max(300,Math.abs(s.vy)*1.08);}}
   path.push({x:s.x,y:s.y});if(s.x>current().hoop.x+100||s.y>GROUND+100||hits>12)break
 }
 return{path,hits,apex}
}
function shoot(a,p){
 if(ball?.active||levelShots>=MAX_ATTEMPTS)return;
 levelShots++;totalShots++;updateAttemptUI();
 const v=velocity(a,p),startTime=movingClock;
 ball={...ballStart(),vx:v.vx,vy:v.vy,active:true,path:[],collisions:0,t:0,startTime};
 lastShot={angle:a*180/Math.PI,power:p,spin,startTime};
 preview=simulate(v,startTime).path;
 ui.angle.textContent=lastShot.angle.toFixed(1)+"°";ui.power.textContent=Math.round(p*100)+"%";ui.spin.textContent=spin.toFixed(1);
 ui.result.textContent="出手！";ui.detail.textContent=current().tip;updateLab(null);
}
function diagnose(scored,shot,collisionCount){
 if(scored)return"很好：这条轨迹解决了本关的核心问题。下一关会增加一个新的决策。";
 const target=current().hoop.x-START.x;
 if(shot.power<.38)return"力度偏低：先保证球有足够的水平距离，再微调角度。";
 if(shot.power>.92)return"力度偏高：球可能越过篮筐，先降低力量，再保持角度。";
 if(shot.angle<.35)return"弧线偏低：尝试抬高仰角，尤其注意障碍物的顶部。";
 if(shot.angle>.95)return"弧线偏高：球在到达篮筐前消耗了太多水平距离。";
 if(collisionCount>3)return"碰撞次数较多：你可能让球连续撞击了错误的表面，先简化路线。";
 if(shot.startTime!==undefined&&current().obs.some(o=>o.move))return"角度和力量接近了，下一球可以观察移动障碍的窗口。";
 if(target>900)return"路线接近成功：保持大方向，只做小幅力量调整。";
 return"这次没有进筐。下一球只改一个变量，更容易找到原因。";
}
function showRunComplete(){
 ui.modalLabel.textContent="RUN COMPLETE";
 ui.modalTitle.textContent="你完成了这一局";
 ui.modalText.textContent=`10 个节点全部完成 · 命中 ${made} 次 · 总出手 ${totalShots} 次 · 最终构筑 ${ui.buildSummary.textContent}`;
 ui.rewardList.innerHTML='<button class="reward-option run-complete" id="restartAfterWin"><strong>再来一局</strong><span>保留当前规则，重新从 Node 1 开始。</span><em>RESET RUN</em></button>';
 ui.rewardModal.classList.remove("hidden");
 document.getElementById("restartAfterWin").onclick=resetRun;
}
function showRewards(){
 ui.modalLabel.textContent="BUILD REWARD";ui.modalTitle.textContent="选择一个物理构筑";ui.modalText.textContent="奖励会改变下一关的投法，而不是直接增加命中率。";ui.rewardList.innerHTML=REWARDS.map(r=>`<button class="reward-option" data-reward="${r.id}"><strong>${r.name}</strong><span>${r.desc}</span><em>${r.tag} · 当前 ${build[r.id]} 层</em></button>`).join("");
 ui.rewardModal.classList.remove("hidden");
 ui.rewardList.querySelectorAll("[data-reward]").forEach(btn=>btn.onclick=()=>chooseReward(btn.dataset.reward));
}
function chooseReward(id){
 build[id]++;ui.rewardModal.classList.add("hidden");renderBuild();ui.tip.textContent="构筑已加入 · 下一关开始";next();
}
function loseLife(){
 hp--;
 renderRunMap();
 if(hp<=0){
   runEnded=true;
   ui.modalLabel.textContent="RUN OVER";
   ui.modalTitle.textContent="这局结束了";
   ui.modalText.textContent=`你在 Node ${level+1} 用尽了生命。构筑没有保留到下一局。`;
   ui.rewardList.innerHTML='<button class="reward-option run-complete" id="restartAfterLoss"><strong>重新开始</strong><span>清空本局构筑，从 Node 1 再次挑战。</span><em>NEW RUN</em></button>';
   ui.rewardModal.classList.remove("hidden");
   document.getElementById("restartAfterLoss").onclick=resetRun;
   return;
 }
 ui.tip.textContent=`生命 -1 · 剩余 ${hp} · 重试当前节点`;
 reset();
}
function resetRun(){
 if(advanceTimer){clearTimeout(advanceTimer);advanceTimer=null}
 level=0;levelShots=0;totalShots=0;made=0;spin=0;hp=3;runEnded=false;for(const k of Object.keys(build))build[k]=0;ui.made.textContent=0;ui.rewardModal.classList.add("hidden");reset();
}
function finish(scored,reason){
 const shot=lastShot;const collisions=ball?ball.collisions:0;ball=null;preview=[];
 if(scored)made++;
 ui.made.textContent=made;ui.result.textContent=scored?"SWISH!":"MISS";
 ui.detail.textContent=diagnose(scored,shot,collisions);
 updateLab(shot?{...shot,scored,collisions}:null);
 if(scored){
  if(level===levels.length-1){runEnded=true;ui.tip.textContent="RUN COMPLETE · 你完成了全部 10 个节点";showRunComplete();}
  else{ui.tip.textContent="NODE CLEAR · 选择一个构筑，然后进入下一关";showRewards();}
 } else if(levelShots>=MAX_ATTEMPTS){
   ui.tip.textContent=hp>1?"本节点失败 · 消耗 1 HP 并重试":"本节点失败 · 生命耗尽";
   ui.result.textContent=hp>1?"LIFE LOST":"RUN OVER";
   setTimeout(()=>{if(!runEnded)loseLife()},700);
 }
}
function queueNext(){if(advanceTimer)return;advanceTimer=setTimeout(()=>{advanceTimer=null;next()},ADVANCE_DELAY)}
function updateLab(s){
 ui.distance.textContent=s?((current().hoop.x-START.x)/100).toFixed(2)+" m":"—";
 if(!s){ui.apex.textContent="—";ui.collision.textContent="—";ui.outcome.textContent="—";ui.diagnosis.textContent="每次出手后，这里会告诉你下一球该观察什么。";return}
 const sim=simulate(velocity(s.angle*Math.PI/180,s.power),s.startTime);
 ui.apex.textContent=((START.y-sim.apex)/100).toFixed(2)+" m";ui.collision.textContent=String(s.collisions??sim.hits)+" 次";
 ui.outcome.textContent=s.scored?"命中":"未命中";ui.diagnosis.textContent=diagnose(s.scored,s,s.collisions??sim.hits)
}
function next(){
 if(advanceTimer){clearTimeout(advanceTimer);advanceTimer=null}
 if(runEnded)return;
 if(level<levels.length-1){level++;reset()}
}
function draw(){
 ctx.clearRect(0,0,W,H);drawBackground();drawCourt();drawHoop();drawObstacles();drawPlayer();
 if(!ball?.active)drawPreview();else drawFlight();if(drag)drawAim(drag)
}
function drawBackground(){
 const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,"#182330");g.addColorStop(1,"#0d1218");ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 ctx.fillStyle="#202a32";for(let x=0;x<W;x+=80)ctx.fillRect(x,GROUND,78,H-GROUND);
 ctx.strokeStyle="#354351";ctx.lineWidth=2;for(let x=0;x<W;x+=80){ctx.beginPath();ctx.moveTo(x,GROUND);ctx.lineTo(x,H);ctx.stroke()}
 ctx.fillStyle="#71808c";ctx.font="14px monospace";ctx.fillText("2D PHYSICS COURT",24,52)
}
function drawCourt(){ctx.strokeStyle="#566572";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,GROUND);ctx.lineTo(W,GROUND);ctx.stroke();ctx.fillStyle="#7b8994";ctx.font="12px monospace";ctx.fillText("START",118,GROUND+28)}
function drawHoop(){
 const h=current().hoop;ctx.strokeStyle="#dce5ec";ctx.lineWidth=7;ctx.beginPath();ctx.moveTo(h.x+55,h.y-85);ctx.lineTo(h.x+55,h.y+35);ctx.stroke();
 ctx.strokeStyle="#ff8d3a";ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(h.x-42,h.y,h.x+42,h.y);ctx.stroke();
 ctx.strokeStyle="#d8e1e8";ctx.lineWidth=2;for(let i=-35;i<=35;i+=18){ctx.beginPath();ctx.moveTo(h.x+i,h.y+3);ctx.lineTo(h.x+i*.65,h.y+42);ctx.stroke()}
 ctx.beginPath();ctx.moveTo(h.x-24,h.y+42);ctx.lineTo(h.x+24,h.y+42);ctx.stroke()
}
function drawObstacles(){
 for(const o of obstacleSnapshot()){ctx.fillStyle=o.t==="bar"?"#d89a4b":o.t==="wall"?"#53738e":"#657083";ctx.strokeStyle="#a9b8c5";ctx.lineWidth=2;ctx.fillRect(o.x,o.y,o.w,o.h);ctx.strokeRect(o.x,o.y,o.w,o.h);
  ctx.fillStyle="#dbe4eb";ctx.font="11px monospace";ctx.fillText(o.t==="bar"?"ARC":"BOUNCE",o.x+5,o.y+18)
 }
}
function drawPlayer(){
 const x=145,y=GROUND-18;ctx.strokeStyle="#f2a64a";ctx.lineWidth=7;ctx.lineCap="round";ctx.beginPath();ctx.arc(x,y-66,15,0,Math.PI*2);ctx.stroke();
 ctx.beginPath();ctx.moveTo(x,y-50);ctx.lineTo(x,y-12);ctx.moveTo(x,y-40);ctx.lineTo(x+24,y-62);ctx.moveTo(x,y-38);ctx.lineTo(x-22,y-20);ctx.moveTo(x,y-12);ctx.lineTo(x-18,y+5);ctx.moveTo(x,y-12);ctx.lineTo(x+19,y+4);ctx.stroke()
}
function drawAim(d){
 const b=ball||ballStart(),a=getAim(d),len=a.len;ctx.setLineDash([8,7]);ctx.strokeStyle="#79c8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x+Math.cos(a.angle)*len,b.y-Math.sin(a.angle)*len);ctx.stroke();ctx.setLineDash([]);
 ctx.fillStyle="#79c8ff";ctx.font="bold 14px monospace";ctx.fillText((a.angle*180/Math.PI).toFixed(1)+"°",b.x+15,b.y-18);
 drawPreview(a.angle,a.power)
}
function drawPreview(a,p){
 if(a===undefined){if(!lastShot)return;a=lastShot.angle*Math.PI/180;p=lastShot.power}
 const sim=simulate(velocity(a,p),movingClock);ctx.fillStyle="#6fc1ff";for(let i=0;i<sim.path.length;i+=6){const q=sim.path[i];ctx.beginPath();ctx.arc(q.x,q.y,2.2,0,Math.PI*2);ctx.fill()}
}
function drawFlight(){
 const b=ball;if(b.path.length>2){ctx.strokeStyle="#ffca72";ctx.lineWidth=3;ctx.beginPath();b.path.forEach((q,i)=>i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y));ctx.stroke()}
 ctx.fillStyle="#e77b2d";ctx.beginPath();ctx.arc(b.x,b.y,BALL_R,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#4d2b19";ctx.lineWidth=2;ctx.stroke();
}
function tick(now){
 const dt=Math.min(.025,(now-lastTime)/1000);lastTime=now;movingClock+=dt;
 if(ball?.active){
  const prev={x:ball.x,y:ball.y};ball.vy+=G*dt;ball.x+=ball.vx*dt;ball.y+=ball.vy*dt;ball.t+=dt;ball.path.push({x:ball.x,y:ball.y});
  if(ball.y+BALL_R>GROUND){ball.y=GROUND-BALL_R;ball.vy=-Math.abs(ball.vy)*.64;ball.vx*=.92;ball.collisions++}
  if(ball.x-BALL_R<0){ball.x=BALL_R;ball.vx=Math.abs(ball.vx)*.72;ball.collisions++}
  for(const o of obstacleSnapshot(ball.startTime+ball.t)){if(circleRect(ball,o)){resolveRect(ball,o);ball.collisions++}}
  if(circleRect(ball,boardRect())){resolveRect(ball,boardRect());ball.collisions++;
   if(build.secondChance>0&&!secondChanceUsed){secondChanceUsed=true;ball.vy=-Math.max(300,Math.abs(ball.vy)*1.08);ui.detail.textContent="二次机会触发：第一次篮筐碰撞没有结束这球。";}}
  if(hoopScore(ball,prev))finish(true,"");
  else if(ball.t>4.8||ball.y>GROUND+80||ball.x>W+80||ball.collisions>9)finish(false,"")
 }
 draw();requestAnimationFrame(tick)
}
canvas.addEventListener("pointerdown",e=>{if(ball?.active||levelShots>=MAX_ATTEMPTS)return;drag=pointer(e);canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener("pointermove",e=>{if(drag)drag=pointer(e)});
canvas.addEventListener("pointerup",e=>{if(!drag)return;const p=pointer(e),a=getAim(p);drag=null;if(a.len<18)return;shoot(a.angle,a.power)});
canvas.addEventListener("pointercancel",()=>{drag=null});
canvas.addEventListener("wheel",e=>{e.preventDefault();spin=Math.max(-8,Math.min(8,spin+(e.deltaY<0?.5:-.5)));ui.spin.textContent=spin.toFixed(1)},{passive:false});
document.getElementById("reset").onclick=reset;document.getElementById("resetRun").onclick=resetRun;document.getElementById("next").onclick=next;
ui.made.textContent=made;renderBuild();renderRunMap();reset();requestAnimationFrame(tick);
if(typeof module!=="undefined")module.exports={levels,current,reset,shoot,simulate,hoopScore,next,tick};
